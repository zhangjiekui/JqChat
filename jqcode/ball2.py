import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import RegularPolygon, Circle
import matplotlib.patches as patches

class BouncingBall:
    def __init__(self, hex_radius=5, ball_radius=0.3, gravity=-9.8, dt=0.016):
        self.hex_radius = hex_radius
        self.ball_radius = ball_radius
        self.gravity = gravity
        self.dt = dt
        self.friction = 0.99  # 每帧保留99%的速度
        self.restitution = 0.8  # 碰撞后保持80%的速度
        
        # 六边形参数
        self.hex_angle = 0
        self.angular_speed = 30  # 度/秒
        
        # 球的初始状态
        self.ball_pos = np.array([0.0, 0.0])  # 从中心开始
        # 随机初始速度
        angle = np.random.uniform(0, 2*np.pi)
        speed = 5
        self.ball_vel = np.array([speed * np.cos(angle), speed * np.sin(angle)])
        
        # 轨迹记录
        self.trail = []
        self.max_trail_length = 20
        
    def get_hexagon_vertices(self, angle_deg):
        """计算旋转后六边形的顶点"""
        angle_rad = np.radians(angle_deg)
        vertices = []
        for i in range(6):
            base_angle = 60 * i - 30  # 调整初始角度使边是平的
            x = self.hex_radius * np.cos(np.radians(base_angle) + angle_rad)
            y = self.hex_radius * np.sin(np.radians(base_angle) + angle_rad)
            vertices.append([x, y])
        return np.array(vertices)
    
    def point_to_line_distance(self, point, line_start, line_end):
        """计算点到线段的距离和最近点"""
        line_vec = line_end - line_start
        point_vec = point - line_start
        line_len = np.dot(line_vec, line_vec)
        
        if line_len == 0:
            return np.inf, line_start
        
        # 投影因子
        t = np.dot(point_vec, line_vec) / line_len
        t = max(0, min(1, t))  # 限制在0-1之间
        
        # 最近点
        closest = line_start + t * line_vec
        
        # 距离
        distance = np.linalg.norm(point - closest)
        
        return distance, closest
    
    def check_collision(self):
        """检测球与六边形墙的碰撞"""
        vertices = self.get_hexagon_vertices(self.hex_angle)
        min_distance = np.inf
        collision_normal = None
        collision_point = None
        
        # 检查每条边
        for i in range(6):
            p1 = vertices[i]
            p2 = vertices[(i + 1) % 6]
            
            # 计算到这条边的距离
            dist, closest = self.point_to_line_distance(self.ball_pos, p1, p2)
            
            if dist < min_distance:
                min_distance = dist
                collision_point = closest
                
                # 计算法向量（指向内部）
                edge_vec = p2 - p1
                normal = np.array([-edge_vec[1], edge_vec[0]])  # 垂直向量
                normal = normal / np.linalg.norm(normal)
                
                # 确保法向量指向内部
                center_to_ball = self.ball_pos - np.array([0, 0])
                if np.dot(normal, center_to_ball) < 0:
                    normal = -normal
                
                collision_normal = normal
        
        # 如果距离小于球半径，发生碰撞
        if min_distance < self.ball_radius:
            # 将球移到接触点
            overlap = self.ball_radius - min_distance
            self.ball_pos += collision_normal * overlap
            
            # 反射速度
            vel_norm = np.linalg.norm(self.ball_vel)
            if vel_norm > 0:
                # 反射
                self.ball_vel = self.ball_vel - 2 * np.dot(self.ball_vel, collision_normal) * collision_normal
                # 应用能量损失
                self.ball_vel *= self.restitution
            
            return True
        
        return False
    
    def update_physics(self):
        """更新物理状态"""
        # 更新六边形角度
        self.hex_angle += self.angular_speed * self.dt
        
        # 应用重力
        self.ball_vel[1] += self.gravity * self.dt
        
        # 应用摩擦力
        self.ball_vel *= self.friction
        
        # 更新位置
        self.ball_pos += self.ball_vel * self.dt
        
        # 检查碰撞
        self.check_collision()
        
        # 更新轨迹
        self.trail.append(self.ball_pos.copy())
        if len(self.trail) > self.max_trail_length:
            self.trail.pop(0)
    
    def draw(self, ax):
        """绘制当前状态"""
        ax.clear()
        
        # 绘制六边形
        hexagon = RegularPolygon((0, 0), 6, radius=self.hex_radius, 
                               orientation=np.radians(self.hex_angle),
                               facecolor='none', edgecolor='navy', linewidth=3)
        ax.add_patch(hexagon)
        
        # 绘制轨迹
        if len(self.trail) > 1:
            trail_array = np.array(self.trail)
            ax.plot(trail_array[:, 0], trail_array[:, 1], 
                   'r-', alpha=0.5, linewidth=1)
        
        # 绘制球
        ball = Circle(self.ball_pos, radius=self.ball_radius, 
                     facecolor='red', edgecolor='darkred', linewidth=2)
        ax.add_patch(ball)
        
        # 设置图形属性
        ax.set_xlim(-self.hex_radius-1, self.hex_radius+1)
        ax.set_ylim(-self.hex_radius-1, self.hex_radius+1)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        ax.set_title(f'旋转角度: {self.hex_angle:.1f}°', fontsize=12)
        
        # 隐藏坐标轴
        ax.set_xticks([])
        ax.set_yticks([])

def animate(frame, ball, ax):
    """动画帧函数"""
    ball.update_physics()
    ball.draw(ax)
    return []

# 创建弹跳球实例
ball = BouncingBall()

# 创建图形
fig, ax = plt.subplots(figsize=(8, 8))
fig.patch.set_facecolor('white')

# 创建动画
anim = FuncAnimation(fig, lambda frame: animate(frame, ball, ax), 
                    frames=300, interval=16, blit=True)

# 保存为GIF
print("正在生成动画...")
anim.save('bouncing_ball_hexagon.gif', 
         writer=PillowWriter(fps=60),
         progress_callback=lambda i, n: print(f'帧 {i+1}/{n}'))
print("动画保存完成: bouncing_ball_hexagon.gif")

# 显示最终状态
ball.draw(ax)
plt.show()

# 打印一些统计信息
print(f"\n模拟统计:")
print(f"最终位置: ({ball.ball_pos[0]:.2f}, {ball.ball_pos[1]:.2f})")
print(f"最终速度: ({ball.ball_vel[0]:.2f}, {ball.ball_vel[1]:.2f})")
print(f"最终速度大小: {np.linalg.norm(ball.ball_vel):.2f}")
