from langchain_community.graph_vectorstores import CassandraGraphVectorStore
# pip install "cassio>=0.1.7"
import cassio
# 假设你已经有一个运行中的Cassandra容器，并且你知道其contact points
contact_points = ['10.1.150.105']  # 根据你的Cassandra部署情况修改
# contact_points = ['127.0.0.1']

port = 9042  # Cassandra默认端口
username = 'cassandra'  # Cassandra用户名
password = 'password123'  # Cassandra密码
# 初始化集群和会话
from cassandra.cluster import Cluster
# cluster = Cluster(contact_points=["127.0.0.1",'10.1.150.105','cassandra'], port=9042)  # 使用API代理服务提高访问稳定性
cluster = Cluster(contact_points=['10.1.150.105'], port=9042)  
cluster = Cluster(contact_points=['localhost'], port=9042)  
session = cluster.connect('Test')
# 初始化Cassio客户端
