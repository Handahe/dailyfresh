from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
# 添加商品到购物车
# 1）请求方式采用ajax post
# 如果涉及到数据修改采用post（新增，更新，删除）
# 如果只涉及到数据获取采用get
# 2）传递参数:商品id（sku_id）,商品数量（count）

# Create your views here.

# /cart/add
class CartAddView(View):
    '''购物车记录添加'''
    def post(self,request):
        '''购物车记录添加'''
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0, 'errmsg':'清先登陆'})
        # 接收数据
        sku_id =request.POST.get('sku_id')
        count = request.POST.get('count')
        # 数据校验
        if not all([sku_id, count]):
            return JsonResponse({'res':1, 'errmsg':'数据不完整'})

        # 校验数据添加数量
        try:
            count = int(count)
        except Exception as e:
            # 数目出错
            return JsonResponse({'res':2, 'errmsg':'商品数目出错'})

        # 校验商品书否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res':3, 'errmsg':'商品不存在'})

        # 业务处理：添加购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id
        # 先获取sku_id值
        cart_count = conn.hget(cart_key,sku_id)
        if cart_count:
            # 累加
            count += int(cart_count)

        # 校验库存
        if count >sku.stock:
            return JsonResponse({'res':4,'errmsg':'库存不足'})
        # 设置hash中sku_id对应的值
        conn.hset(cart_key,sku_id,count)
        # 计算用户购物车商品的条目数
        total_count = conn.hlen(cart_key)
        # 返回应答
        return JsonResponse({'res':5, 'total_count':total_count,'errmsg':'添加成功'})

# /cart/
class CartInfoView(LoginRequiredMixin, View):
    '''购物车页面显示'''
    def get(self,request):
        # 获取登录的用户
        user = request.user
        # 获取用户购物车中商品的信息
        conn = get_redis_connection('default')
        cont_key = 'cart_%d' % user.id
        # {'商品id':商品数量,...}
        cart_dict = conn.hgetall(cont_key)
        # 遍历获取商品的信息
        skus = []
        # 保存用户购物车中的总数目和总价格
        total_count = 0
        total_price = 0
        for sku_id,count in cart_dict.items():
            # 根据商品id获取商品的信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 计算商品的小计
            amount = sku.price*int(count)
            # 动态给sku对象添加一个属性amount,保存商品的小计
            sku.amount = amount
            # 动态给sku对象添加一个属性count,保存购物车中对应的商品的数量
            sku.count = count
            skus.append(sku)

            # 累加计算商品总数目和总价格
            total_count += int(count)
            total_price += amount

        # 组织上下文
        context = {'total_count':total_count,
                   'total_price':total_price,
                   'skus':skus}

        return render(request ,'cart.html',context)

# 更新购物车记录
# 采用ajax post请求
# 前端需要传递的参数，商品id（sku_id）更新后的商品数量（count）
# /cart/update
class CartUpdateView(View):
    '''购物车记录更新'''
    def post(self, request):
        user = request.user
        # 获取用户购物车中商品的信息
        if not user.is_authenticated():
            return JsonResponse({'res':0,'errmsg':'请先登录'})
        # 接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        print(count)
        print(sku_id)
        # 数据校验
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        # 校验数据添加数量
        try:
            count = int(count)
        except Exception as e:
            # 数目出错
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})

        # 校验商品书否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})
        # 业务处理：更新购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 先获取sku_id值
        # 校验库存
        if count > sku.stock:
            return JsonResponse({'res':4, 'errmsg':'商品库存不足'})
        # 更新
        conn.hset(cart_key, sku_id, count)

        # 购物车商品总件数
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count+=int(val)
        return JsonResponse({'res':5,'total_count':total_count,'errmsg':'更新成功'})

# 删除购物车记录
# 采用ajax post请求
# 前端需要传递的参数：商品id
# /cart/delete
class CartDeleteView(View):
    '''购物车记录删除'''
    def post(self,request):
        user = request.user
        # 获取用户购物车中商品的信息
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登录'})
        # 接受参数
        sku_id = request.POST.get('sku_id')
        # 数据校验
        if not sku_id:
            return JsonResponse({'res':1, 'errmsg':'无效商品'})
        try:
            sku = GoodsSKU.objects.get(id = sku_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在
            return JsonResponse({'res':2,'errmsg':'商品不存在'})
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        conn.hdel(cart_key,sku_id)

        # 购物车商品总件数
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)

        return JsonResponse({'res':3 ,'total_count':total_count,'errmsg':'删除成功'})


