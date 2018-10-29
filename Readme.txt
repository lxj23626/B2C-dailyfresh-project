- 实现功能：
    - 类视图
    - mysql存储表数据
    - django用户认证
    - celery异步任务队列+redis充当broker实现异步发送注册激活邮件
    - 使用itsdangerous加密用户的身份信息
    - redis存储session，历史浏览记录，购物车商品
    - mysql+FastDFS分布式文件系统+nginx存储商品图片
    - nginx+celery实现页面静态化
    - haystack全文搜索框架+whoosh搜索引擎+jieba分词模块实现搜索商品关键字
    - mysql事务+乐观锁实现订单并发问题
    - 对接支付宝平台实现付款
    - uwsgi+nginx+django实现项目部署
    - nginx搭建负载均衡服务器实现负载均衡





- 启动redis服务端：
    sudo redis-server /etc/redis/redis.conf

- 启动mysql数据库：
    mysql -u root -p 123

- 启动FastDFS的tracker和storage，不开不能上传图片：
    sudo service fdfs_trackerd start
    sudo service fdfs_storaged start

- 启动FastDFS的nginx：
    sudo /usr/local/nginx/sbin/nginx

- 打开Celery：
    celery -A celery_tasks.tasks worker -l info

- 启动mac的Nginx：
    sudo nginx（nginx命令在/usr/local/bin目录下）

- mac的Nginx配置文件路径：
    /usr/local/etc/nginx/nginx.conf