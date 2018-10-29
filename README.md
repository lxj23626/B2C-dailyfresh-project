# B2C购物商城项目
# 实现商品浏览，根据关键字搜索商品，加入购物车，用支付宝付款，评价商品等功能。
# 
# - 使用 mysql存储表结构数据
# - 使用 Django的AbstractUser自定义用户认证模块
# - 使用 celery异步任务队列 + redis充当broker 实现异步发送注册激活邮件
# - 使用 itsdangerous加密用户的身份信息
# - 使用 redis存储session，历史浏览记录，购物车商品
# - 使用 mysql + FastDFS分布式文件系统 + nginx存储商品图片
# - 使用nginx+celery实现页面静态化
# - 使用haystack全文搜索框架+whoosh搜索引擎+jieba分词模块实现搜索商品关键字
# - 使用mysql事务+乐观锁实现订单并发问题
# - 对接支付宝平台实现付款
# - 使用uwsgi+nginx+django实现项目部署
# - 使用nginx搭建负载均衡服务器实现负载均衡
