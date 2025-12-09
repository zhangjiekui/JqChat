import matplotlib
# matplotlib.use('TkAgg')  # 或者 'Qt5Agg'
# matplotlib.use('Qt5Agg')  # 或者 'Qt5Agg'
# matplotlib.use('QtAgg')  # 或者 'Qt5Agg'
# matplotlib.use('Agg')  # 或者 'Qt5Agg'
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle, RegularPolygon
import matplotlib.backends.qt_compat
print(matplotlib.backends.qt_compat.QT_API)
print(matplotlib.get_backend())


# 设置中文字体和负号显示
plt.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 物理参数
HEXAGON_RADIUS = 5.0  # 六边形外接圆半径
BALL_RADIUS = 0.3     # 小球半径
GRAVITY = np.array([0.0, -9.8])  # 重力加速度
AIR_FRICTION = 0.995  # 空气阻力/摩擦系数 (每帧速度衰减)
RESTIUTION = 0.85     # 碰撞恢复系数
ANGULAR_VELOCITY = 1.5  # 六边形旋转角速度 (rad/s)

# 初始状态
ball_pos = np.array([0.0, 2.0])  # 小球初始位置
ball_vel = np.array([5.0, 0.0])  # 小球初始速度
hex_rotation = 0.0  # 六边形当前旋转角度

def get_hexagon_vertices(rotation_angle):
    """计算旋转后六边形的顶点坐标"""
    vertices = []
    for i in range(6):
        # 六边形每个顶点间隔60度 (π/3 弧度)
        angle = rotation_angle + i * np.pi / 3
        x = HEXAGON_RADIUS * np.cos(angle)
        y = HEXAGON_RADIUS * np.sin(angle)
        vertices.append([x, y])
    return np.array(vertices)

def point_to_line_distance(point, p1, p2):
    """计算点到线段的距离和最近点"""
    line_vec = p2 - p1
    point_vec = point - p1
    
    # 计算投影参数 t
    line_len_sq = np.dot(line_vec, line_vec)
    if line_len_sq < 1e-10:
        return np.linalg.norm(point - p1), p1
    
    t = np.dot(point_vec, line_vec) / line_len_sq
    t = np.clip(t, 0.0, 1.0)
    
    # 最近点
    closest = p1 + t * line_vec
    distance = np.linalg.norm(point - closest)
    
    return distance, closest

def check_wall_collision(ball_pos, ball_vel, ball_radius, vertices, dt):
    """检测并处理与所有墙壁的碰撞"""
    new_pos = ball_pos.copy()
    new_vel = ball_vel.copy()
    collision_occurred = False
    
    # 检查每个墙壁 (六边形有6条边)
    for i in range(6):
        p1 = vertices[i]
        p2 = vertices[(i + 1) % 6]
        
        # 墙壁法向量 (指向内部)
        wall_tangent = p2 - p1
        wall_normal = np.array([wall_tangent[1], -wall_tangent[0]])
        norm = np.linalg.norm(wall_normal)
        if norm < 1e-10:
            continue
        
        wall_normal = wall_normal / norm
        
        # 确保法向量指向内部 (朝向中心)
        center_dir = - (p1 + p2) / 2  # 指向中心的方向
        if np.dot(wall_normal, center_dir) < 0:
            wall_normal = -wall_normal
        
        # 计算小球到墙壁的距离
        dist, closest_point = point_to_line_distance(ball_pos, p1, p2)
        
        # 如果距离小于小球半径，发生碰撞
        if dist < ball_radius:
            # 将小球推出墙壁
            penetration = ball_radius - dist
            new_pos += wall_normal * penetration
            
            # 计算碰撞点处的墙壁速度 (由于旋转)
            # 在2D中，角速度引起的线速度: v = ω × r
            # 对于2D: ω 是标量，方向垂直于平面
            # v_wall = (-ω*y, ω*x)
            collision_point = closest_point
            wall_vel = np.array([
                -ANGULAR_VELOCITY * collision_point[1],
                ANGULAR_VELOCITY * collision_point[0]
            ])
            
            # 相对速度
            rel_vel = new_vel - wall_vel
            
            # 如果小球正在进入墙壁 (相对速度指向内部)
            if np.dot(rel_vel, wall_normal) < 0:
                # 反射速度向量
                # v_new = v - 2 * (v·n) * n
                normal_vel = np.dot(rel_vel, wall_normal)
                new_rel_vel = rel_vel - 2 * normal_vel * wall_normal
                
                # 应用恢复系数和添加墙壁速度
                new_vel = wall_vel + RESTIUTION * new_rel_vel
                collision_occurred = True
    
    return new_pos, new_vel, collision_occurred

def update_physics(ball_pos, ball_vel, vertices, dt):
    """更新物理状态"""
    # 1. 应用重力
    new_vel = ball_vel + GRAVITY * dt
    
    # 2. 应用空气阻力/摩擦
    new_vel *= AIR_FRICTION
    
    # 3. 更新位置
    new_pos = ball_pos + new_vel * dt
    
    # 4. 检测并处理碰撞
    new_pos, new_vel, collision = check_wall_collision(
        new_pos, new_vel, BALL_RADIUS, vertices, dt
    )
    
    return new_pos, new_vel

# 创建图形
fig, ax = plt.subplots(figsize=(8, 8))
ax.set_aspect('equal')
ax.set_xlim(-7, 7)
ax.set_ylim(-7, 7)
ax.axis('off')
ax.set_title('小球在旋转六边形中的弹跳', fontsize=14, pad=20)

# 创建图形元素
hexagon_patch = RegularPolygon(xy=(0, 0), numVertices=6, radius=HEXAGON_RADIUS, 
                               orientation=hex_rotation, 
                               facecolor='lightgray', 
                               edgecolor='black', 
                               linewidth=2)
ball_patch = Circle(ball_pos, BALL_RADIUS, facecolor='red', edgecolor='darkred')

ax.add_patch(hexagon_patch)
ax.add_patch(ball_patch)

def animate(frame):
    global ball_pos, ball_vel, hex_rotation
    
    dt = 1/60  # 60 FPS
    
    # 更新六边形旋转角度
    hex_rotation += ANGULAR_VELOCITY * dt
    vertices = get_hexagon_vertices(hex_rotation)
    
    # 更新物理
    ball_pos, ball_vel = update_physics(ball_pos, ball_vel, vertices, dt)
    
    # 更新图形
    # hexagon_patch.set_orientation(hex_rotation)
    hexagon_patch.orientation = hex_rotation
    ball_patch.center = ball_pos
    
    return hexagon_patch, ball_patch

# 创建动画
ani = animation.FuncAnimation(
    fig, animate, 
    frames=1000,  # 总帧数
    interval=16,  # 约60 FPS (16ms)
    blit=True
)

ani.save('bouncing_ball5.gif', writer='pillow', fps=60)
print("动画已保存为bouncing_ball5.gif")



# import pygame
# import math

# # Initialize Pygame
# pygame.init()

# # Constants
# WIDTH, HEIGHT = 600, 600
# FPS = 60
# HEXAGON_RADIUS = 250
# BALL_RADIUS = 15
# GRAVITY = 0.5
# FRICTION = 0.98
# BOUNCE_DAMPING = 0.8
# ROTATION_SPEED = 1  # degrees per frame

# # Colors
# BLACK = (0, 0, 0)
# WHITE = (255, 255, 255)
# RED = (255, 0, 0)
# BLUE = (0, 0, 255)

# class Ball:
#     def __init__(self, x, y):
#         self.x = x
#         self.y = y
#         self.vx = 0
#         self.vy = 0
#         self.radius = BALL_RADIUS
    
#     def update(self):
#         # Apply gravity
#         self.vy += GRAVITY
        
#         # Apply friction
#         self.vx *= FRICTION
#         self.vy *= FRICTION
        
#         # Update position
#         self.x += self.vx
#         self.y += self.vy
        
#         # Check collision with hexagon walls
#         center_x, center_y = WIDTH // 2, HEIGHT // 2
#         dx = self.x - center_x
#         dy = self.y - center_y
#         distance = math.sqrt(dx**2 + dy**2)
        
#         # Hexagon "radius" at current angle
#         angle = math.atan2(dy, dx)
#         hex_radius_at_angle = HEXAGON_RADIUS * math.cos(math.pi / 6) / math.cos(angle % (math.pi / 3) - math.pi / 6)
        
#         if distance + self.radius > hex_radius_at_angle:
#             # Normalize collision normal
#             nx = dx / distance
#             ny = dy / distance
            
#             # Position correction
#             overlap = distance + self.radius - hex_radius_at_angle
#             self.x -= nx * overlap
#             self.y -= ny * overlap
            
#             # Reflect velocity with damping
#             dot_product = self.vx * nx + self.vy * ny
#             self.vx = (self.vx - 2 * dot_product * nx) * BOUNCE_DAMPING
#             self.vy = (self.vy - 2 * dot_product * ny) * BOUNCE_DAMPING

# def get_hexagon_vertices(center_x, center_y, radius, rotation_angle):
#     vertices = []
#     for i in range(6):
#         angle = math.radians(60 * i + rotation_angle)
#         x = center_x + radius * math.cos(angle)
#         y = center_y + radius * math.sin(angle)
#         vertices.append((x, y))
#     return vertices

# def main():
#     screen = pygame.display.set_mode((WIDTH, HEIGHT))
#     pygame.display.set_caption("Bouncing Ball in Spinning Hexagon")
#     clock = pygame.time.Clock()
    
#     # Create ball
#     ball = Ball(WIDTH // 2, HEIGHT // 4)
    
#     # Initial rotation angle
#     rotation_angle = 0
    
#     running = True
#     while running:
#         for event in pygame.event.get():
#             if event.type == pygame.QUIT:
#                 running = False
        
#         # Update rotation
#         rotation_angle += ROTATION_SPEED
        
#         # Update ball physics
#         ball.update()
        
#         # Drawing
#         screen.fill(BLACK)
        
#         # Calculate hexagon vertices
#         center_x, center_y = WIDTH // 2, HEIGHT // 2
#         vertices = get_hexagon_vertices(center_x, center_y, HEXAGON_RADIUS, rotation_angle)
        
#         # Draw hexagon
#         pygame.draw.polygon(screen, WHITE, vertices, 3)
        
#         # Draw ball
#         pygame.draw.circle(screen, RED, (int(ball.x), int(ball.y)), ball.radius)
        
#         # Add trail effect
#         pygame.draw.circle(screen, BLUE, (int(ball.x), int(ball.y)), ball.radius - 5)
        
#         pygame.display.flip()
#         clock.tick(FPS)
    
#     pygame.quit()

# if __name__ == "__main__":
#     main()
