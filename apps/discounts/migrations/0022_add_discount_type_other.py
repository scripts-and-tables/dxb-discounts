from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('discounts', '0021_in_house_chain_loyalty'),
    ]

    operations = [
        migrations.AlterField(
            model_name='discount',
            name='discount_type',
            field=models.CharField(
                choices=[
                    ('percentage', 'Percentage off'),
                    ('bogo', 'Buy one get one (2-for-1)'),
                    ('fixed_price', 'Fixed price deal'),
                    ('promo_code', 'Promo code / voucher'),
                    ('other', 'Special offer'),
                ],
                max_length=20,
            ),
        ),
    ]
