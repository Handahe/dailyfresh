from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate, login, logout
from django.views.generic import View
from django.http import HttpResponse
from django.conf import settings
from django.core.paginator import Paginator

from user.models import User, Address
from goods.models import GoodsSKU
from order.models import OrderInfo,OrderGoods

from celery_tasks.tasks import send_register_active_email
import re
from utils.mixin import LoginRequiredMixin
from django.core.mail import send_mail  # 发邮件
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer  # 发邮件时信息加密
from itsdangerous import SignatureExpired  # 信息过期异常
from django_redis import get_redis_connection


# Create your views here.

class RegisterView(View):
    '''注册'''

    def get(self, request):
        '''显示注册页面'''
        return render(request, 'register.html')

    def post(self, request):
        '''进行注册处理'''
        # 接受数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        cpwd = request.POST.get('cpwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 进行数据校验
        if not all([username, password, email]):
            # 校验数据是否完整
            return render(request, 'register.html', {'errmsg': '数据不完整'})
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            # 校验邮箱
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})
        if password != cpwd:
            # 密码两次是否一致校验
            return render(request, 'register.html', {'errmsg': '两次密码不一致'})
        if allow != 'on':
            # 校验是否勾选同意协议
            return render(request, 'register.html', {'errmsg': '请同意协议'})
        try:
            # 校验用户名是否重复
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在
            user = None
        if user:
            return render(request, 'register.html', {'errmsg': '用户名已存在'})
        # 进行业务处理：进行用户注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 发送激活邮件，包含激活链接：http://127.0.0.1:8000/user/active/id
        # 激活链接中包含用户信息，并且要把身份信息加密

        # 加密用户的身份信息，生成token
        serializer = Serializer(settings.SECRET_KEY,3600)
        info = {'confirm':user.id}
        token = serializer.dumps(info) # 返回一个bytes的数据格式
        token = token.decode() # 转换成utf8格式，默认就是utf8格式

        # 发邮件
        # subject = '天天生鲜欢迎信息'
        # message = '邮件正文'
        # sender = settings.EMAIL_FROM
        # receiver = [email]
        # html_message = '<h1>%s,欢迎</h1><br>请点击以下链接激活<br><a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>'%(username, token, token)
        #
        # send_mail(subject, message, sender, receiver, html_message= html_message)

        # send_register_active_email.delay(email, username, token)
        # 返回应答,跳转到首页
        return redirect(reverse('goods:index'))


class ActiveView(View):
    '''用户激活'''

    def get(self, request, token):
        '''进行用户激活'''
        # 获取要激活的用户信息
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            # 获取激活用户的id
            user_id = info['confirm']
            # 根据id获取用户信息,修改保存的用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            # 返回应答，跳转到登录页面
            return redirect(reverse('user:login'))

        except SignatureExpired as e:
            # 激活连接已过期
            return HttpResponse('激活连接已过期')


# # /user/login
class LoginView(View):
#     '''显示登录页面'''
#
    def get(self, request):
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request, 'login.html', {'username': username, 'checked': checked})
#
    def post(self, request):
        # 接收数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        remember = request.POST.get('remember')
        # 校验数据
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg': '数据不完整'})
        # 业务处理：登陆校验
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                # 用户已激活
                # 记录登陆的状态
                login(request, user)
                # 获取登陆后要跳转的地址默认跳转到首页
                next_url = request.GET.get('next', reverse('goods:index'))
                # 跳转到
                response = redirect(next_url)
                # 判断是否需要记录用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    response.set_cookie('username', username, max_age=7 * 24 * 3600)
                else:
                    response.delete_cookie('username')
                # 返回response
                return response
            else:
                # 用户未激活
                return render(request, 'login.html', {'errmsg': '用户未激活'})
        else:
            # 不存在用户或在密码不正确
            return render(request, 'login.html', {'errmsg': '用户名或密码不正确'})
#
#
class LogoutView(View):
    '''退出登陆'''
    def get(self, request):
        logout(request)
        return redirect(reverse('goods:index'))

# /user LoginRequiredMixin,
class UserInfoView(LoginRequiredMixin,View):
#     '''用户中心信息页'''
#
    def get(self, request):
#         '''显示'''
#         # 判断用户是否登陆
#         # page=‘user’
#         # request.user
#         # 如果用户登陆就会返回一个user实例——返回ture
#         # 如果用户未登录返回一个AnonymousUser的实例返回false
#         # request.user.is_authenticated()
#         #
#         # 获取用户个人信息
#         #
        user = request.user
        address = Address.objects.get_default_address(user)
#
        # 获取历史浏览记录
#         # 原本的方式
#         #from redis import StrictRedis
#         #sr=StrictRedis(host='127.0.0.1',port='6379',db=9)
        con = get_redis_connection('default')  # 使用django_redis的方式
#
        history_key = 'history_%d' % user.id
        # 获取用户最新浏览的五条商品
        sku_ids = con.lrange(history_key, 0, 4)
        # 从数据库中查询用户浏览商品具体信息
        # goods_li = GoodsSKU.objects.filter(id__in=sku_ids)
        # goods_res = []
        # for a_id in sku_ids:
        #    for goods in good_li:
        #        if a_id == goods.id:
        #            goods_res.append(goods)
        goods_li = []
        for sku_id in sku_ids:
            goods = GoodsSKU.objects.get(id=sku_id)
            goods_li.append(goods)
        # 组织上下文
        context = {'page': 'user',
                   'address': address,
                   'goods_li': goods_li}
#
#         # 除了给模板传递的变量之外，框架会把request.user也传给模板文件
        return render(request, 'user_center_info.html', context)


# /user/order LoginRequiredMixin,
class UserOrderView(LoginRequiredMixin,View):
    '''用户中心订单页'''

    def get(self, request, page):
        '''显示'''
        # 获取用户的订单的信息
        user = request.user
        orders = OrderInfo.objects.filter(user= user).order_by('-create_time')
        # 遍历orders获取订单商品信息
        for order in orders:
            # 根据order_id查询订单商品信息
            order_skus = OrderGoods.objects.filter(order_id = order.order_id)
            # 遍历计算每个商品的小计
            for order_sku in order_skus:
                # 计算商品小计
                amount = order_sku.count*order_sku.price
                # 动态给order_sku增加属性，保存订单商品的小计
                order_sku.amount = amount
            # 订单状态
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
            # 动态给order增加属性，保存订单商品信息
            order.order_skus = order_skus

        # 分页
        paginator = Paginator(orders,1)
        # 处理页码
        # 获取第page的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1
        if page > paginator.num_pages:
            page = 1
        # 获取第page页的Page实例对象
        order_page = paginator.page(page)

        # todo: 进行页码的控制，页面最多显示五个页码
        # 1，总页数<5页，页面显示所有页码
        # 2. 如果当前页是前三页，显示1-5页
        # 3. 如果当前页是后三也，显示后五页页码
        # 4. 显示当前页的前两页，当前页，当前页的后两页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 组织上下文
        context = {'order_page':order_page,
                   'pages':pages,
                   'page': 'order'}

        return render(request, 'user_center_order.html', context)


# /user/addressLoginRequiredMixin,
class AddressView(LoginRequiredMixin,View):
#     '''用户中心地址页'''
#
    def get(self, request):
        '''显示'''
        # 获取用户的默认地址信息
        user = request.user  # 获取user对象
        # try:
        #    address = Address.objects.get(user=user,is_default=True)
        # except Address.DoesNotExist:
        #不存在默认收货地址
           # address = None
        address = Address.objects.get_default_address(user)
        # 使用模板
        return render(request, 'user_center_site.html', {'page': 'address', 'address': address})
#
    def post(self, request):
        '''用户收件地址'''
        # 接收数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')
        # 校验数据
        if not all([receiver, addr, phone]):
            return render(request, 'user_center_site.html', {'errmsg': '数据不完整'})
        if not re.match(r'^1[3|4|5|7|8]\d{9}$', phone):
            return render(request, 'user_center_site.html', {'errmsg': '手机号不正确'})
        # 地址添加（业务处理）
        # 如果没有默认收货地址，将添加的作为默认地址
        user = request.user  # 获取user对象
        # try:
        #     address = Address.objects.get(user=user,is_default=True)
        # except Address.DoesNotExist:
            # 不存在默认收货地址
            # address = None
        address = Address.objects.get_default_address(user)
        if address:
            is_default = False
        else:
            is_default = True

        # 添加地址
        Address.objects.create(user=user,
                               receiver=receiver,
                               addr=addr,
                               zip_code=zip_code,
                               phone=phone,
                               is_default=is_default)
        # 返回应答,刷新地址
        return redirect(reverse('user:address'))
