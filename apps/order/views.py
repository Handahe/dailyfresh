from django.shortcuts import render,redirect
from django.core.urlresolvers import reverse
from django.views.generic import View
from django.db import transaction
from django.http import JsonResponse
from django.conf import settings

from goods.models import GoodsSKU
from user.models import Address
from order.models import OrderInfo,OrderGoods


from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
from datetime import datetime
from alipay import AliPay
import os

# Create your views here.
# /order/place
class OrderPlaceView(LoginRequiredMixin, View):
    '''提交订单页面显示'''
    def post(self, request):
        # 获取登陆的用户
        user = request.user
        # 获取参数
        sku_ids = request.POST.getlist('sku_ids')
        # 校验参数
        if not sku_ids:
            return redirect(reverse('cart:show'))
        # 遍历sku_ids 获取每个用户的信息

        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        skus = []
        # 保存商品的总件数和总价格
        total_count = 0
        total_price = 0
        # 遍历sku_ids 获取用户要购买的商品信息
        for sku_id in sku_ids:
            # 根据商品的id获取商品的信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 获取用户购买的数量
            count = conn.hget(cart_key,sku_id)
            # 计算商品的小计
            amount = sku.price*int(count)
            # 动态给sku增加属性
            sku.count = count
            sku.amount = amount
            skus.append(sku)
            # 累加计算商品的总价格和总件数
            total_count += int(count)
            total_price += int(amount)

        # 运费：实际开发的时候，属于一个子系统
        transit_price = 10  # 写死了
        # 是付款
        total_pay = total_price + transit_price

        # 获取用户的收件地址
        addrs = Address.objects.filter(user=user)

        # 将用户购买的商品id拼接成一个字符串
        sku_ids = ','.join(sku_ids)
        # 组织上下文
        context = {'skus':skus,
                   'total_count':total_count,
                   'total_price':total_price,
                   'transit_price':transit_price,
                   'total_pay':total_pay,
                   'addrs':addrs,
                   'sku_ids':sku_ids}
        # 使用模板
        return render(request, 'place_order.html', context)

# 前端传递的参数：地址id（addr_id）支付方式（pay_method）用户要购买的商品id字符串（sku_ids）
class OrderCommitView1(View):
    '''订单创建'''
    @transaction.atomic
    def post(self,request):
        # 判断用户是否登陆
        user = request.user

        if not user.is_authenticated():
            # 用户未登录
            return JsonResponse({'res':0,'errmsg':'用户未登录'})
        # 接收参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')
        # 校验参数
        if not all([addr_id,pay_method,sku_ids]):
            return JsonResponse({'res':1,'errmsg':'数据不完整'})
        # 校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res':2,'errmsg':'支付方式不存在'})
        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            # 地址不存在
            return JsonResponse({{'res':3,'errmsg':'地址不存在'}})

        # todo:创建业务核心业务

        # 组织参数
        # 订单id（年月日时分秒+用户id）
        order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)
        # 运费
        transit_price = 10
        # 总数目和总金额
        total_count = 0
        total_price = 0

        # 设置保存点
        save_id = transaction.savepoint()
        try:
            # todo:向df_order_info表中添加一条数据
            order = OrderInfo.objects.create(order_id=order_id,
                                     user=user,
                                     addr=addr,
                                     pay_method=pay_method,
                                     transit_price=transit_price,
                                     total_price=total_price,
                                     total_count=total_count)

            # todo:用户订单中有几个商品，需要向df_order_goods表中添加几条数据
            conn = get_redis_connection('default')
            cart_key= 'cart_%d'%user.id

            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                # 获取商品信息
                try:
                    # select * from df_goods_sku where id=sku_id for update;
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    # 商品不存在
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res':4,'errmsg':'没有该商品'})

                # 从redis中获取用户所购买的商品数量
                count = conn.hget(cart_key,sku_id)
                # todo:判断商品库存
                if int(count) > sku.stock:
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res':6,'errmsg':'商品库存不足'})

                # todo:向df_order_goods表中加一条数据
                OrderGoods.objects.create(order=order,
                                          sku=sku,
                                          count=count,
                                          price=sku.price)
                # todo:更新商品的库存和销量
                sku.stock -= int(count)
                sku.sales += int(count)
                sku.save()

                # todo:累加计算订单商品的总数目与总价格
                amount = sku.price*int(count)
                total_count +=int(count)
                total_price +=amount

            # todo: 更新订单表中的商品总数量和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res':7,'errmsg':'下单失败'})
        # todo:清除用户购物车中对应的商品记录
        transaction.savepoint_commit(save_id)
        conn.hdel(cart_key,*sku_ids)
        # 返回应答
        return JsonResponse({'res':5,'errmsg':'创建成功'})

class OrderCommitView(View):
    '''订单创建'''
    @transaction.atomic
    def post(self,request):
        # 判断用户是否登陆
        user = request.user

        if not user.is_authenticated():
            # 用户未登录
            return JsonResponse({'res':0,'errmsg':'用户未登录'})
        # 接收参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')
        # 校验参数
        if not all([addr_id,pay_method,sku_ids]):
            return JsonResponse({'res':1,'errmsg':'数据不完整'})
        # 校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res':2,'errmsg':'支付方式不存在'})
        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            # 地址不存在
            return JsonResponse({{'res':3,'errmsg':'地址不存在'}})

        # todo:创建业务核心业务

        # 组织参数
        # 订单id（年月日时分秒+用户id）
        order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)
        # 运费
        transit_price = 10
        # 总数目和总金额
        total_count = 0
        total_price = 0

        # 设置保存点
        save_id = transaction.savepoint()
        try:
            # todo:向df_order_info表中添加一条数据
            order = OrderInfo.objects.create(order_id=order_id,
                                     user=user,
                                     addr=addr,
                                     pay_method=pay_method,
                                     transit_price=transit_price,
                                     total_price=total_price,
                                     total_count=total_count)

            # todo:用户订单中有几个商品，需要向df_order_goods表中添加几条数据
            conn = get_redis_connection('default')
            cart_key= 'cart_%d'%user.id

            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                for i in range(3):
                    # 获取商品信息
                    try:
                        # select * from df_goods_sku where id=sku_id for update;
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except GoodsSKU.DoesNotExist:
                        # 商品不存在
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res':4,'errmsg':'没有该商品'})

                    # 从redis中获取用户所购买的商品数量
                    count = conn.hget(cart_key,sku_id)

                    # todo:判断商品库存
                    if int(count) > sku.stock:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res':6,'errmsg':'商品库存不足'})

                    # todo:更新商品的库存和销量
                    orgin_stock = sku.stock
                    new_stock = orgin_stock - int(count)
                    new_sales = sku.sales + int(count)

                    # update df_goods_sku set stock=new_stock,sales=new_sales
                    # where id=sku_id and stock=orgin_stock
                    # 返回受影响的行数
                    res = GoodsSKU.objects.filter(id=sku_id,stock=orgin_stock).update(stock=new_stock, sales=new_sales)
                    if res==0:
                        if i == 2:
                            transaction.savepoint_rollback(save_id)
                            return JsonResponse({'res':7,'errmsg':'下单失败'})
                        continue


                    # todo:向df_order_goods表中加一条数据
                    OrderGoods.objects.create(order=order,
                                              sku=sku,
                                              count=count,
                                              price=sku.price)



                    # todo:累加计算订单商品的总数目与总价格
                    amount = sku.price*int(count)
                    total_count +=int(count)
                    total_price +=amount

                    # 跳出循环
                    break

            # todo: 更新订单表中的商品总数量和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res':7,'errmsg':'下单失败'})
        # todo:清除用户购物车中对应的商品记录
        transaction.savepoint_commit(save_id)
        conn.hdel(cart_key,*sku_ids)
        # 返回应答
        return JsonResponse({'res':5,'errmsg':'下单成功'})


# ajax post
# 前端传递的参数：订单id（order_id）
# /order/pay
class OrderPayView(View):
    '''订单支付'''
    def post(self,request):
        '''订单支付'''
        # 用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0,'errmsg':'用户未登录'})
        # 接收参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not order_id:
            return JsonResponse({'res':1,'errmsg':'订单id不存在'})
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res':2,'errmsg':'订单不存在'})
        # 业务处理，使用python sdk调用支付宝的支付接口
        # 初始化

        app_private_key_string = open(os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem')).read()
        alipay_public_key_string = open(os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem')).read()
        alipay = AliPay(
            appid='2016102200740783',
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key_string,
            alipay_public_key_string=alipay_public_key_string,  # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False ,若开启则使用沙盒环境的支付宝公钥
        )

        # 调用支付接口
        # 通过Web支付，在浏览器中打开以下URL：https: // openapi.alipaydev.com / gateway.do？+ order_string
        total_pay = order.total_price+order.transit_price
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id, # 订单id
            total_amount=str(total_pay), # 支付总金额
            subject='天天生鲜%s'%order_id,
            return_url=None,
            notify_url=None  # this is optional
        )
        pay_url = 'https://openapi.alipaydev.com/gateway.do?'+order_string
        # 返回应答
        return JsonResponse({'res':3,'pay_url':pay_url})


# ajax post
# 前端传递的参数：订单id(order_id)
# /order/check
class OrderCheckView(View):
    def post(self,request):
        '''访问支付宝获取订单交易信息'''
        # 用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 接收参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '订单id不存在'})
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单不存在'})
        # 业务处理，使用python sdk调用支付宝的支付接口
        # 初始化

        app_private_key_string = open(os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem')).read()
        alipay_public_key_string = open(os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem')).read()
        alipay = AliPay(
            appid='2016102200740783',
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key_string,
            alipay_public_key_string=alipay_public_key_string,  # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False ,若开启则使用沙盒环境的支付宝公钥
        )

        # 调用支付宝交易查询接口
        while True:
            response = alipay.api_alipay_trade_query(order_id)
            # 取值
            code = response.get('code')

            if code == '10000' and response.get('trade_status') == 'TRADE_SUCCESS':
                # 支付成功
                # 获取支付宝交易号
                trade_no = response.get('trade_no')
                # 更新订单的状态
                order.trade_no = trade_no
                order.order_status = 4 # 待评价
                order.save()
                # 返回应答
                return JsonResponse({'res':3,'message':'支付成功'})
            elif code == '10000' and response.get('trade_status') == 'WAIT_BUYER_PAY':
                # 等待买家付款
                import time
                time.sleep(5)
            else:
                # 支付失败
                return JsonResponse({'res':4,'message':'支付失败'})

# /order/comment
class OrderCommentView(View):
    def get(self, request, order_id):
        user = request.user
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id,user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))

        # 根据订单状态获取东单状态标题
        order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
        # 获取订单商品信息
        order_skus = OrderGoods.objects.filter(order_id=order_id)
        for order_sku in order_skus:
            # 计算商品小计
            amount = order_sku.count*order_sku.price
            # 动态给order_sku 添加属性amount
            order_sku.amount = amount
        # 动态给order添加属性order_skus,保存订单商品信息
        order.order_skus = order_skus
        # 返回渲染模板
        return render(request,'order_comment.html',{'order':order})

    def post(self, request, order_id):
        '''处理评论内容'''
        user =request.user
        if not order_id:
            return redirect(reverse('user:order'))
        try:
            order = OrderInfo.objects.get(order_id=order_id,user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))
        # 获取条数
        total_count = request.POST.get('total_count')
        total_count = int(total_count)

        for i in range(1, total_count+1):
            # 获取被评论商品id
            sku_id = request.POST.get('sku_%d'%i)
            # 评论商品内容
            content = request.POST.get('content_%d'%i,'')

            try:
                order_goods = OrderGoods.objects.get(order_id=order_id,sku_id=sku_id)
            except OrderGoods.DoesNotExist:
                continue
            order_goods.comment = content
            order_goods.save()


        order.order_status = 5
        order.save()

        return redirect(reverse('user:order',kwargs={'page':1}))














