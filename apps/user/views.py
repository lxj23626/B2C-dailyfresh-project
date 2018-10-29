from django.shortcuts import render, redirect, HttpResponse
from django.views.generic import View
import re
from django.conf import settings
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer, SignatureExpired
from celery_tasks.tasks import send_register_active_email
from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate, login, logout
from utils.mixin import LoginRequiredMixin
from apps.user.models import User, Address
from apps.goods.models import GoodsSKU
from apps.order.models import OrderInfo, OrderGoods
from django_redis import get_redis_connection
from django.core.paginator import Paginator

# Create your views here.

# /user/register
class RegisterView(View):
    '''注册'''

    def get(self, request):
        '''显示注册页面'''
        return render(request, 'register.html')

    def post(self, request):
        ''' 进行注册处理 '''
        #### 接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        #### 进行数据校验
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        # 校验邮箱
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})

        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)      # 不报错代表用户名存在
        except User.DoesNotExist:
            user = None                                     # 用户名不存在

        if user:
            return render(request, 'register.html', {'errmsg': '用户名已存在'})

        #### 进行业务处理: 进行用户注册
        user = User.objects.create_user(username, email, password)      # 使用create_user()方法进行注册用户
        user.is_active = 0
        user.save()

        # todo:发送激活邮件，包含激活链接: http://127.0.0.1:8000/user/active/........
        # todo:激活链接中需要包含用户的身份信息, 并且要把身份信息进行加密

        # 利用itsdangerous加密用户的身份信息，生成激活token
        serializer = Serializer(settings.SECRET_KEY, 3600)  # 激活链接一小时后失效
        info = {'confirm': user.id}
        token = serializer.dumps(info)  # bytes
        token = token.decode()

        # 发邮件
        send_register_active_email.delay(email, username, token)

        # 返回应答, 跳转到首页
        return redirect(reverse('goods:index'))


class ActiveView(View):
    '''用户激活'''
    def get(self, request, token):
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)      # 进行解密，获取要激活的用户信息，返回字典
            user_id = info['confirm']           # 获取待激活用户的id

            # 根据id获取用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()

            # 跳转到登录页面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            return HttpResponse('激活链接已过期')
        except Exception as e:
            # 防止用户乱填激活链接
            return HttpResponse('激活链接无效')


# /user/login
class LoginView(View):
    '''登录'''
    def get(self, request):
        '''显示登录页面'''
        #### 判断是否已经登录
        if request.user.is_authenticated():
            return redirect(request.GET.get('next', reverse('goods:index')))

        #### 判断是否记住用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''

        # 使用模板
        return render(request, 'login.html', {'username':username, 'checked':checked})

    def post(self, request):
        '''登录校验'''
        #### 接收数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        #### 校验数据
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg':'数据不完整'})

        user = authenticate(username=username, password=password)           # 登录校验
        if user:        # 用户名密码正确
            if user.is_active:
                login(request, user)    # 用户已激活，记录用户的登录状态
                next_url = request.GET.get('next', reverse('goods:index'))  # 获取登录后所要跳转到的地址，默认跳转到首页

                #  将跳转到next_url
                response = redirect(next_url)   # HttpResponseRedirect

                # 判断是否需要记住用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    # 记住用户名
                    response.set_cookie('username', username, max_age=7*24*3600)    # 一周有效
                else:
                    response.delete_cookie('username')

                # 返回response
                return response
            else:
                # 用户未激活
                return render(request, 'login.html', {'errmsg':'账户未激活'})
        else:
            # 用户名或密码错误
            return render(request, 'login.html', {'errmsg':'用户名或密码错误'})


# /user/logout
class LogoutView(View):
    '''退出登录'''
    def get(self, request):
        logout(request)     # 清除用户的session信息

        return redirect(reverse('goods:index'))     # 跳转到首页


# /user
class UserInfoView(LoginRequiredMixin, View):
    '''用户中心-信息页'''
    def get(self, request):
        '''显示'''
        # Django会给request对象添加一个属性request.user
        # 如果用户未登录->user是AnonymousUser类的一个实例对象，如果用户登录->user是User类的一个实例对象
        # request.user.is_authenticated()

        #### 获取用户的个人信息
        user = request.user
        # print(111,user)
        # print(222,type(user))
        address = Address.objects.get_default_address(user)

        #### 获取用户的历史浏览记录
        # from redis import StrictRedis
        # sr = StrictRedis(host='172.16.179.130', port='6379', db=9)
        con = get_redis_connection('default')

        history_key = 'history_%d' %user.id

        #### 获取用户最新浏览的5个商品的id
        sku_ids = con.lrange(history_key, 0, 4) # [2,3,1]

        #### 从数据库中查询用户浏览的商品的具体信息，直接通过商品id从数据库获取信息会导致商品顺序不正确，可用以下两种方法：
        # goods_li = GoodsSKU.objects.filter(id__in=sku_ids)
        #
        # goods_res = []
        # for a_id in sku_ids:
        #     for goods in goods_li:
        #         if a_id == goods.id:
        #             goods_res.append(goods)

        # 遍历获取用户浏览的商品信息，比较简单，但是要查询多次数据库
        goods_li = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_li.append(goods)

        # 组织上下文
        context = {
            'page': 'user',
            'address': address,
            'goods_li': goods_li,
        }

        # request.user自动传给模板文件，不需要手动添加
        return render(request, 'user_center_info.html', context)


# /user/order
class UserOrderView(LoginRequiredMixin, View):
    '''用户中心-订单页'''
    def get(self, request, page):
        '''显示'''
        #### 获取用户的订单信息
        user = request.user
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')   # 该用户的所有订单

        for order in orders:
            # 根据order_id查询订单商品信息
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)     # 某订单所有订单商品

            # 遍历order_skus计算商品的小计
            for order_sku in order_skus:
                # 动态给order_sku增加属性amount
                order_sku.amount = order_sku.count * order_sku.price    # 每个商品的总价

            # 动态给order增加属性，保存订单状态
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]

            # 动态给order增加属性，保存订单的商品信息
            order.order_skus = order_skus

        #### 分页
        paginator = Paginator(orders, 1)

        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的Page实例对象
        order_page = paginator.page(page)

        # todo: 进行页码的控制，页面上最多显示5个页码
        num_pages = paginator.num_pages # 总页数
        if num_pages < 5:               # 1.总页数小于5页，页面上显示所有页码
            pages = range(1, num_pages + 1)
        elif page <= 3:                 # 2.如果当前页是前3页，显示1-5页
            pages = range(1, 6)
        elif num_pages - page <= 2:     # 3.如果当前页是后3页，显示后5页
            pages = range(num_pages - 4, num_pages + 1)
        else:                           # 4.显示当前页的前2页，当前页，当前页的后2页
            pages = range(page - 2, page + 3)

        # 组织上下文
        context = {'order_page':order_page,     # page对象
                   'pages':pages,               # range对象
                   'page': 'order'}

        # 使用模板
        return render(request, 'user_center_order.html', context)


# /user/address
class AddressView(LoginRequiredMixin, View):
    '''用户中心-地址页'''
    def get(self, request):
        '''显示'''
        # 获取登录用户对应User对象
        user = request.user
        address = Address.objects.get_default_address(user)

        # 使用模板
        return render(request, 'user_center_site.html', {'page':'address', 'address':address})

    def post(self, request):
        '''添加地址'''
        #### 接收数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        #### 校验数据
        if not all([receiver, addr, phone, type]):
            return render(request, 'user_center_site.html', {'errmsg':'数据不完整'})

        # 校验手机号
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$', phone):
            return render(request, 'user_center_site.html', {'errmsg':'手机格式不正确'})

        #### 业务处理：地址添加
        # 如果用户已存在默认收货地址，添加的地址不作为默认收货地址，否则作为默认收货地址
        user = request.user
        address = Address.objects.get_default_address(user)

        if address:
            is_default = False      # 已经有默认地址了
        else:
            is_default = True

        # 添加地址
        Address.objects.create(user=user,
                               receiver=receiver,
                               addr=addr,
                               zip_code=zip_code,
                               phone=phone,
                               is_default=is_default)

        # 返回应答,刷新地址页面
        return redirect(reverse('user:address')) # get请求方式