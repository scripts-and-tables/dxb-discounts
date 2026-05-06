from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class DiscountType(models.TextChoices):
    PERCENTAGE = "percentage", "Percentage off"
    BOGO = "bogo", "Buy one get one (2-for-1)"
    FIXED_PRICE = "fixed_price", "Fixed price deal"
    PROMO_CODE = "promo_code", "Promo code / voucher"


class DiscountProgram(models.TextChoices):
    IN_HOUSE = "in_house", "Loyalty program"
    FAZAA = "fazaa", "Fazaa"
    ESAAD = "esaad", "Esaad"
    ENTERTAINER = "entertainer", "Entertainer"


class DiscountQuerySet(models.QuerySet):
    def live(self):
        today = timezone.localdate()
        return self.filter(
            is_active=True,
            place__is_published=True,
        ).filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=today)
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gte=today)
        )

    def featured(self):
        return self.live().filter(is_featured=True)


class Discount(models.Model):
    place = models.ForeignKey(
        "places.Place",
        on_delete=models.CASCADE,
        related_name="discounts",
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)

    percentage = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Used when type is Percentage. e.g. 25 for 25% off.",
    )
    fixed_price_aed = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Used when type is Fixed price. Price in AED.",
    )
    promo_code = models.CharField(
        max_length=64, blank=True,
        help_text="Used when type is Promo code. Code the customer presents/enters.",
    )

    description = models.TextField()
    terms = models.TextField(blank=True, help_text="Fine print, exclusions, hours, etc.")

    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True, help_text="Leave blank for ongoing offers.")

    source_program = models.CharField(
        max_length=20,
        choices=DiscountProgram.choices,
        blank=True,
        default="",
        help_text="Which program/card offers this discount. Leave blank if none.",
    )

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_members_only = models.BooleanField(default=False, help_text="Hidden from anonymous visitors; visible to signed-in users.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DiscountQuerySet.as_manager()

    class Meta:
        ordering = ["-is_featured", "-created_at"]
        indexes = [
            models.Index(fields=["discount_type"]),
            models.Index(fields=["is_active", "is_featured"]),
            models.Index(fields=["valid_until"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} @ {self.place.name}"

    def clean(self):
        super().clean()
        if self.discount_type == DiscountType.PERCENTAGE and not self.percentage:
            raise ValidationError({"percentage": "Required when discount type is Percentage."})
        if self.discount_type == DiscountType.FIXED_PRICE and self.fixed_price_aed is None:
            raise ValidationError({"fixed_price_aed": "Required when discount type is Fixed price."})
        if self.discount_type == DiscountType.PROMO_CODE and not self.promo_code:
            raise ValidationError({"promo_code": "Required when discount type is Promo code."})
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValidationError({"valid_until": "Must be on or after Valid from."})

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or "discount"
            slug = base
            i = 2
            while Discount.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("discounts:detail", kwargs={"slug": self.slug})

    @property
    def headline(self) -> str:
        """Short human label for the deal, e.g. '25% off' or '2-for-1' or 'AED 99'."""
        if self.discount_type == DiscountType.PERCENTAGE and self.percentage:
            return f"{self.percentage}% off"
        if self.discount_type == DiscountType.BOGO:
            return "2-for-1"
        if self.discount_type == DiscountType.FIXED_PRICE and self.fixed_price_aed is not None:
            return f"AED {self.fixed_price_aed:g}"
        if self.discount_type == DiscountType.PROMO_CODE and self.promo_code:
            return f"Code: {self.promo_code}"
        return self.get_discount_type_display()
