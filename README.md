使用DDPG算法实现cartpole 100万次不倒

DDPG的全称是Deep Deterministic Policy Gradient,一种Actor Critic机器增强学习方法
CartPole是http://gym.openai.com/envs/CartPole-v0/ 这个网站提供的一个杆子不倒的测试环境。

CartPole环境返回一个状态包括位置、加速度、杆子垂直夹角和角加速度。玩家控制左右两个方向使杆子不倒。
杆子倒了或超出水平位置限制就结束一个回合。一个回合中杆不倒动作步数越多越好。
cartpole_ddpg 程序是训练出一个DDPG神经网络，用来玩CartPole-v0,使杆子不倒，步数越多越好。
现在程序已可以训练出100万步不倒的网络。
源代码：https://github.com/ccjy88/cartpole_ddpg
