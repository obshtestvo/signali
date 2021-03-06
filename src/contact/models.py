from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.template.defaultfilters import slugify

from unidecode import unidecode
from watson import search as watson
from .apps import setting

class ContactPointManager(models.Manager):
    def apply_criteria(self, score_expression, filters, sorting, term=None, search_backend=None):
        queryset = self.all()
        try:
            queryset = self._transform_criteria_base(queryset)
        except NotImplementedError:
            pass
        queryset = queryset.filter(filters)
        if term:
            queryset = watson.filter(queryset, term, backend_name=search_backend)
        queryset, orderby = self._apply_criteria_sorting(queryset, sorting, score_expression)
        if orderby:
            queryset = queryset.order_by(*orderby)

        return queryset

    def get_by_slug(self, slug):
        return self.get(slug=slug)

    def _apply_criteria_sorting(self, queryset, sorting, score_expression):
        if score_expression != 0:
            queryset = queryset.annotate(score=score_expression)
        return queryset, sorting

    """
    Called before applying criteria with user filters
    """
    def _transform_criteria_base(self, queryset):
        raise NotImplementedError("Your subclcass must implement this")


class BaseContactPoint(models.Model):
    class Meta:
        abstract = True
        verbose_name = _('contact point')
        verbose_name_plural = _('contact points')

    objects = ContactPointManager()

    YES = 'yes'
    NO = 'no'
    DONTKNOW = 'dontknow'
    EXTENDED_BOOLEAN_CHOICES = (
        (YES, _('Yes')),
        (NO, _('No')),
        (DONTKNOW, _("I don't know")),
    )

    title = models.CharField(_('title'), max_length=250, blank=True)
    slug = models.SlugField(_('slug'), max_length=255, blank=True, null=True)
    url = models.URLField(_('URL'), max_length=255, blank=True, null=True)
    source_url = models.URLField(_('Source URL'), max_length=255, blank=True, null=True)
    email = models.EmailField(_('Email'), max_length=255, blank=True, null=True)
    description = models.TextField(_('description'), blank=True)
    notes = models.TextField(_('notes'), blank=True)
    operational_area = models.ForeignKey(setting('CONTACT_AREA_MODEL', noparse=True), related_name="contact_points", verbose_name=_("operational area"), null=True)
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="contactpoint_proposals", verbose_name=_("user that proposed it"), null=True, blank=True)
    response_time = models.PositiveIntegerField(verbose_name=_("Response time"), blank=True, null=True)

    organisation = models.ForeignKey(setting('CONTACT_ORGANISATION_MODEL', noparse=True), related_name="contact_points", verbose_name=_("organisation"), null=True)
    keywords = models.ManyToManyField(setting('CONTACT_KEYWORD_MODEL', noparse=True), related_name="contact_points", verbose_name=_("keywords"))
    category = models.ForeignKey(setting('CONTACT_CATEGORY_MODEL', noparse=True), related_name="contact_points", verbose_name=_("category"))

    # features
    is_multilingual = models.CharField(_('is multilingual'), max_length=20, choices=EXTENDED_BOOLEAN_CHOICES, default=DONTKNOW, blank=True)
    is_response_guaranteed = models.CharField(_('guarantees response'), max_length=20, choices=EXTENDED_BOOLEAN_CHOICES, default=DONTKNOW, blank=True)
    is_verifiable = models.CharField(_('is verifiable'), max_length=20, choices=EXTENDED_BOOLEAN_CHOICES, default=DONTKNOW, blank=True)
    is_confirmation_issued = models.CharField(_('is there a confirmation issued'), max_length=20, choices=EXTENDED_BOOLEAN_CHOICES, default=DONTKNOW, blank=True)
    is_mobile_friendly = models.CharField(_('is mobile friendly'), max_length=20, choices=EXTENDED_BOOLEAN_CHOICES, default=DONTKNOW, blank=True)
    is_final_destination = models.CharField(_('is final destination'), max_length=20, choices=EXTENDED_BOOLEAN_CHOICES, default=DONTKNOW, blank=True)
    is_anonymous_allowed = models.CharField(_('allows anonymous requests'), max_length=20, choices=EXTENDED_BOOLEAN_CHOICES, default=DONTKNOW, blank=True)

    # requirements
    is_registration_required = models.BooleanField(_('required registration'), default=False, blank=True)
    is_photo_required = models.BooleanField(_('photo registration'), default=False, blank=True)
    is_esign_required = models.BooleanField(_('required e-signature'), default=False, blank=True)
    is_name_required = models.BooleanField(_('required name'), default=False, blank=True)
    is_email_required = models.BooleanField(_('required email'), default=False, blank=True)
    is_pic_required = models.BooleanField(_('required personal indentification code'), default=False, blank=True)
    is_address_required = models.BooleanField(_('required address'), default=False, blank=True)
    is_phone_required = models.BooleanField(_('required phone'), default=False, blank=True)
    is_location_required = models.BooleanField(_('required location'), default=False, blank=True)
    is_other_required = models.BooleanField(_('required other'), default=False, blank=True)
    other_requirements = models.TextField(_('other requirements'), blank=True)

    created_at = models.DateTimeField(_('created at'), default=timezone.now)

    def has_downsides(self):
        lacks_features = self.NO in [
            self.is_multilingual,
            self.is_response_guaranteed,
            self.is_verifiable,
            self.is_confirmation_issued,
            self.is_mobile_friendly,
            self.is_final_destination,
            self.is_anonymous_allowed,
        ]
        has_requirements = True in [
            self.is_registration_required,
            self.is_photo_required,
            self.is_esign_required,
            self.is_name_required,
            self.is_email_required,
            self.is_pic_required,
            self.is_address_required,
            self.is_phone_required,
            self.is_location_required,
            self.is_other_required
        ]
        return lacks_features or has_requirements

    def title_or_organisation(self):
        specific = self.title
        if not specific:
            specific = self.organisation.title
        return specific

    def save(self, *args, **kwargs):
        if not self.slug:
            base = self.title if self.title else '{}_{}'.format(self.organisation.title, self.category.title)
            self.slug = slugify(unidecode(base))
        super().save(*args, **kwargs)

    def __str__(self):
        specific = self.title
        if not specific:
            specific = self.organisation.title
        if self.parent:
            specific += ' - ' + self.operational_area.title
        return "{} ({})".format(specific, str(self.category))
    __str__.admin_order_field = 'title'



class BaseOrganisation(models.Model):
    class Meta:
        abstract = True
        verbose_name = _('organisation')
        verbose_name_plural = _('organisations')

    GOVERNMENT = 'gov'
    NGO = 'ngo'
    UNOFFICIAL = 'unofficial'
    COMMERCIAL = 'commercial'
    TYPES = (
        (GOVERNMENT, _('Government')),
        (NGO, _('NGO')),
        (UNOFFICIAL, _("Unofficial")),
        (COMMERCIAL, _("Commercial")),
    )
    type = models.CharField(_('type'), max_length=20, choices=TYPES, default=GOVERNMENT)
    address = models.OneToOneField(setting('CONTACT_AREA_MODEL', noparse=True), blank=True, null=True, on_delete=models.SET_NULL, parent_link=True)
    title = models.CharField(_('title'), max_length=250, blank=False)
    email = models.EmailField(_('email'), max_length=250, blank=True)
    operational_area = models.ForeignKey(setting('CONTACT_AREA_MODEL', noparse=True),
                                         related_name="organisations",
                                         verbose_name=_("operational area"),
                                         blank=True,
                                         null=True,
                                         on_delete=models.SET_NULL)

    @property
    def is_governmental(self):
        return self.type == self.GOVERNMENT

    def __str__(self):
        repr = '{}'
        params = [self.title]
        if self.email:
            repr += ' ({})'
            params.append(self.email)

        return repr.format(*params)
