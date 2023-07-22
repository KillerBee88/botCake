from django.db import models
from datetime import timedelta
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Max
from BakeCake.settings import URGENT_ORDER_ALLOWANCE, BOT_LINK
from bot.bitlink import is_bitlink, shorten_link, count_clicks


class CakeParam(models.Model):
    title = models.CharField('Название', max_length=20) 
    image = models.ImageField('Изображение', null=True, blank=True)
    price = models.DecimalField(
        'Цена',
        default=0.00,
        max_digits=6, decimal_places=2)
    is_available = models.BooleanField('Есть в наличии', default=False)

    class Meta:
        abstract = True


class Level(CakeParam):
    LEVEL_CHOICES = [
        (1, '1 уровень'),
        (2, '2 уровня'),
        (3, '3 уровня')
    ]
    title = models.IntegerField(
        'Количество уровней',
        choices=LEVEL_CHOICES,
        unique=True,
        default=1)
    
    class Meta:
        verbose_name_plural = 'Уровни'

    def __str__(self):
        return str(self.title)


class Shape(CakeParam):
    title = models.CharField('Название формы', max_length=20)

    class Meta:
        verbose_name_plural = 'Форма'


class Topping(CakeParam):
    title = models.CharField('Название топпинга', max_length=20)
    
    class Meta:
        verbose_name_plural = 'Топпинг'


class Berries(CakeParam):
    title = models.CharField('Название ягод', max_length=20)
    
    class Meta:
        verbose_name_plural = 'Ягоды'


class Decor(CakeParam):
    title = models.CharField('Название декора', max_length=20)
    
    class Meta:
        verbose_name_plural = 'Декор'    



class Cake(models.Model):
    is_original = models.BooleanField('Оригинальный', default=False)
    title = models.CharField(
        'Название торта',
        null=True, blank=True,
        max_length=50,
        default=f'Торт')
    image = models.ImageField('Изображение', null=True, blank=True)     
    description = models.TextField('Описание', null=True, blank=True)   

    level = models.ForeignKey(
        Level,
        verbose_name='Уровни',
        null=True,
        on_delete=models.PROTECT)  
    shape = models.ForeignKey(
        Shape,
        verbose_name='Форма',
        null=True,
        on_delete=models.PROTECT)  
    topping = models.ForeignKey(
        Topping,
        verbose_name='Топпинг',
        null=True,
        on_delete=models.PROTECT)  
    berries = models.ForeignKey(
        Berries,
        verbose_name='Ягоды',
        null=True, blank=True,
        on_delete=models.SET_NULL)  
    decor = models.ForeignKey(
        Decor,
        verbose_name='Декор',
        null=True, blank=True,
        on_delete=models.SET_NULL)  
    text = models.CharField(
        'Надпись на торте',
        max_length=100,
        null=True, blank=True)
    
    class Meta:
        verbose_name_plural = 'Торты'

    def __str__(self):
        if self.title:
            return f'Торт {self.title}'
        return f'Торт #{self.id}'

    def get_params(self):
        return [self.level, self.shape,
                self.topping, self.berries, self.topping]

    def get_price(self):
        return f'{sum([param.price if param else 0 for param in self.get_params()])} руб.'

    def get_composition(self):
        message = f'{self.__str__()}\n' \
                  'Состав:\n'\
                  f'Количество уровней: {self.level}\n' \
                  f'Форма коржей: {self.shape.title}\n' \
                  f'Топпинг: {self.topping.title}\n'
        if self.berries:
            message += f'Ягоды: {self.berries.title}\n'
        if self.decor:
            message += f'Декор: {self.decor.title}\n'
        if self.text:
            message += f'Надпись на торте: {self.text}\n'
        message += f'Стоимость торта {self.get_price()}'
        return message

    def verify_cake(self):
        for param in self.get_params():
            if not param.is_available:
                return False
        return True


class Client(models.Model):
    id_telegram = models.CharField('Телеграм id', max_length=20)
    name = models.CharField('Имя', max_length=30, default='Дорогой Гость')
    address = models.CharField('Адрес', max_length=80, null=True, blank=True)
    consent_to_pdProc = models.BooleanField(
        'Согласие на обработку ПД',
        default=False)
    
    class Meta:
        verbose_name_plural = 'Клиенты'

    def __str__(self):
        return f'{self.name}, {self.id_telegram}'


class Complaint(models.Model):
    text = models.TextField('Текст жалобы')
    
    class Meta:
        verbose_name_plural = 'Жалоба'


class PromoCode(models.Model):
    code = models.CharField('Код', unique=True, max_length=20)
    discount = models.DecimalField(
        'Скидка',
        max_digits=3, decimal_places=2,
        validators=[MinValueValidator(0),
                    MaxValueValidator(1)])

    def __str__(self):
        return f'Код "{self.code}" на скидку {self.discount * 100}%'


class Order(models.Model):
    cake = models.ForeignKey(
        Cake,
        verbose_name='Торт',
        on_delete=models.CASCADE)
    client = models.ForeignKey(
        Client,
        verbose_name='Клиент',
        related_name='orders',
        on_delete=models.CASCADE)
    order_dt = models.DateTimeField(
        'Дата и время заказа',
        auto_now_add=True)
    delivery_dt = models.DateTimeField(
        'Дата и время доставки',
        null=True, blank=True)
    address = models.CharField('Адрес', max_length=80, null=True, blank=True)
    promo_code = models.ForeignKey(
        PromoCode,
        verbose_name='Промокод',
        null=True, blank=True,
        on_delete=models.SET_NULL)
    comment = models.TextField('Комментарий', null=True, blank=True)
    complaint = models.OneToOneField(
        Complaint,
        on_delete=models.SET_NULL,
        null=True, blank=True)
    # status
    
    class Meta:
        verbose_name_plural = 'Заказы'

    def is_urgent_order(self):
        delta = self.delivery_dt - self.order_dt
        return  delta < timedelta(days=1)

    def get_price(self):
        cake_price = self.cake.get_params()
        order_price = cake_price * \
                      (1 - self.promo_code.discount) * \
                      (1 + self.is_urgent_order() * URGENT_ORDER_ALLOWANCE)
        return f'{round(order_price, 2)} руб.'

    def get_description(self):
        message = f'{self.__str__()}:\n' \
                  f'{self.cake.__str__()}\n'
        if self.delivery_dt:
            message += f'Доставить {self.delivery_dt}\n'
        if self.address:
            if self.delivery_dt:
                message += f'По адресу {self.address}\n'
            else:
                message += f'Доставить по адресу {self.address}\n'
        message += f'Стоимость заказа {self.get_price()}'
        return message

    def __str__(self):
        return f'Заказ #{self.id} от {self.order_dt}'


def create_new_bitlink():
    max_id = Link.objects.aggregate(Max('id'))['id__max']
    if not max_id:
        max_id = 0
    next_bitlink_id = max_id + 1
    while True:
        if not is_bitlink(BOT_LINK, next_bitlink_id):
            return shorten_link(BOT_LINK, next_bitlink_id)
        next_bitlink_id += 1


class Link(models.Model):
    shorten_link = models.CharField(
        'Сокращенная ссылка',
        max_length=20,
        null=True, blank=True,
        default=create_new_bitlink)
    place_of_use = models.CharField(
        'Место использования ссылки',
        max_length=50,
        null=True, blank=True)

    @property
    def clicks(self):
        return count_clicks(self.shorten_link)


