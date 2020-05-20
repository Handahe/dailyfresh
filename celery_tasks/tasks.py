# 使用celery
from django.conf import settings
from django.core.mail import send_mail
from django.template import loader,RequestContext
from celery import Celery
import time
# 在任务处理者一
#
# 端加的代码
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")
django.setup()

from goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner

# 创建一个实例对象
app = Celery('celery_tasks.tasks', broker='redis://127.0.0.1:6379/8')
# 定义任务函数，发邮件函数
@app.task
def send_register_active_email(to_email, username, token):
    '''发送激活邮件'''
    # 组织邮件信息
    subject = '天天生鲜欢迎信息'
    message = ''
    sender = settings.EMAIL_FROM
    receiver = [to_email]
    html_message = '<h1>%s,欢迎</h1><br>请点击以下链接激活<br><a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>'%(username, token, token)
    send_mail(subject, message, sender, receiver, html_message=html_message)

@app.task
def generate_static_index_html():
    '''产生首页静态页面'''
    types = GoodsType.objects.all()
    # 获取首页轮播图信息
    goods_banners = IndexGoodsBanner.objects.all().order_by('index')
    # 获取首页促销信息
    promotion_banners = IndexPromotionBanner.objects.all().order_by('index')
    # 获取首页分类商品展示信息
    #type_goods_banners = IndexTypeGoodsBanner.objects.all()
    for type in types:

    # 获取type种类首页分类商品图片信息
        image_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')
    # 获取type种类首页分类商品的文字展示信息
        title_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')
    # 将查出来的数据动态添加到type中
        type.image_banners = image_banners
        type.title_banners = title_banners
    # 获取用户购物车中商品信息
    # 组织模范上下文
    context = {'types': types,
               'goods_banners': goods_banners,
               'promotion_banners': promotion_banners}

    # 加载模板文件
    temp = loader.get_template('static_index.html')
    # 定义模板上下文
    # 模板渲染
    statoc_index_html = temp.render(context)

    save_path = os.path.join(settings.BASE_DIR, 'static/static_index/index.html')
    with open(save_path,'w',encoding='utf-8') as f:
        f.write(statoc_index_html)










