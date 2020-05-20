# 定义索引类
from haystack import indexes
# 导入模型类
from goods.models import GoodsSKU

# 指定对于某个类的某些数据建立索引
# 索引类名为：模型类名+Index
class GoodsSKUIndex(indexes.SearchIndex, indexes.Indexable):
    # 索引字段use_template=True指定根据表中的那个字段建立索引文件,把说明房子一个文件中
    text = indexes.CharField(document=True, use_template=True)

    def get_model(self):  # 重载get_model方法，必须要有！
        return GoodsSKU
    # 建立索引数据
    def index_queryset(self, using=None): #重载get_model方法，必须要有！
        return self.get_model().objects.all()