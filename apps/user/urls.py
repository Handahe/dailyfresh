from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from user.views import RegisterView, ActiveView, LoginView, LogoutView, UserInfoView, UserOrderView, AddressView

urlpatterns = (
    # url(r'^register$', views.register, name='register'), # 注册、注册处理
    url(r'^register$', RegisterView.as_view(), name='register'),  # 注册、注册处理
    url(r'^active/(?P<token>.*)$', ActiveView.as_view(), name='active'), # 用户激活
    url(r'^login$', LoginView.as_view(), name='login'), # 用户登录页面
    url(r'^logout$', LogoutView.as_view(), name='logout'), # 用户退出登陆

    # url(r'^$', login_required(UserInfoView.as_view()), name='user'), # 用户中心信息页面
    # url(r'^order$', login_required(UserOrderView.as_view()), name='order'), # 用户中心订单页面
    # url(r'^address$', login_required(AddressView.as_view()), name='address'), # 用户中心地址页面

    url(r'^$', UserInfoView.as_view(), name='user'), # 用户中心信息页面
    url(r'^order/(?P<page>\d+)$', UserOrderView.as_view(), name='order'), # 用户中心订单页面
    url(r'^address$', AddressView.as_view(), name='address'), # 用户中心地址页面
)