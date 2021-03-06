from django.contrib import admin
from django import forms
from django.utils.translation import ugettext_lazy as _

from sorl.thumbnail.admin import AdminImageMixin
from adminextra.reverseadmin import ReverseModelAdmin
from django_bootstrap_datetimepicker.widgets import BootstrapDateTimeInput
from suit.widgets import AutosizedTextarea

from contact.admin import BaseContactPointAdmin
from signali_location.models import Area
from signali_taxonomy.models import Category
from location.forms import AreaAutosuggestWidget
from .models import ContactPoint, ContactPointGrouped, Organisation, SignalContactPointFeedback

betterDateTimePicker = BootstrapDateTimeInput(format="%d.%m.%Y %H:%M")

extended_booelan_fields = [
    'is_multilingual',
    'is_response_guaranteed',
    'is_verifiable',
    'is_confirmation_issued',
    'is_mobile_friendly',
    'is_final_destination',
    'is_anonymous_allowed',
]


class ContactPointForm(forms.ModelForm):
    class Meta:
        model = ContactPointGrouped
        exclude = []
        widgets = {
            "other_requirements": AutosizedTextarea(),
        }

    force_required = extended_booelan_fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["category"].queryset = Category.objects.children()
        self.fields["title"].label = _('specific name')
        self.fields["title"].help_text = _("If it's different than the organisation")
        for fieldname in self.fields:
            if fieldname in self.force_required:
                self.fields[fieldname].choices = ContactPoint.EXTENDED_BOOLEAN_CHOICES



class ContactPointChildForm(forms.ModelForm):
    class Meta:
        model = ContactPointGrouped
        exclude = []
        widgets = {
            'operational_area': AreaAutosuggestWidget,
            'description': AutosizedTextarea,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["operational_area"].required = True

class ContactPointChildAdmin(admin.StackedInline):
    model = ContactPointGrouped
    form = ContactPointChildForm
    suit_classes = 'suit-tab suit-tab-children'
    verbose_name = _('branch')
    verbose_name_plural = _('branches')
    extra = 1
    fieldsets = (
        (None, {'fields': [
            'operational_area',
            'url',
            'email',
            'source_url',
            'description',
        ]}),
    )


class ContactPointAdmin(BaseContactPointAdmin, AdminImageMixin):
    form = ContactPointForm
    inlines = (ContactPointChildAdmin,)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(parent=None)

    def save_related(self, request, form, formsets, change):
        for formset in formsets:
            for childform in formset.forms:
                if not childform.cleaned_data:
                    continue
                childform.instance.parent = form.instance
                childform.instance = childform.instance.get_synced_copy_of_parent(form.instance)
        super().save_related(request, form, formsets, change)

    prepopulated_fields = {"slug": ("title",)}
    suit_form_tabs = (
        ('basic', _('basic')),
        ('children', _('branches')),
        ('visibility', _('visibility')),
        ('user-proposed', _('proposed by user')),
    )

    def children_count(self, obj):
        return obj.children.count()
    children_count.short_description = _('Number of branches')

    radio_fields = dict((field, admin.HORIZONTAL) for field in extended_booelan_fields)

    list_per_page = 40
    list_display = ('__str__', 'children_count', 'category', 'is_featured', 'is_public',)
    list_editable = ('is_featured', 'is_public', )
    list_display_links = ('__str__',)
    list_filter = (
        ('category', admin.RelatedOnlyFieldListFilter),
        'keywords',
        'is_public',
    )
    search_fields = ('organisation__title', 'title', 'description',)

    fieldsets = (

        (None, {
            'classes': ('suit-tab suit-tab-basic',),
            'fields': ('organisation', 'title', 'slug', 'is_public',)
        }),
        (_('key content'), {
            'classes': ('suit-tab suit-tab-basic',),
            'fields': ('category', 'keywords')
        }),
        #@todo move children inline here? (by changing form html http://stackoverflow.com/questions/18734924/how-to-position-inlines-in-django-admin)
        (_('features'), {
            'classes': ('suit-tab suit-tab-basic',),
            'fields': extended_booelan_fields
        }),
        (_('requirements'), {
            'classes': ('suit-tab suit-tab-basic',),
            'fields': (
                           'is_registration_required',
                           'is_photo_required',
                           'is_esign_required',
                           'is_name_required',
                           'is_email_required',
                           'is_phone_required',
                           'is_pic_required',
                           'is_address_required',
                           'is_location_required',
                           'is_other_required',
                           'other_requirements',
                       )
        }),
        (_('visuals'), {
            'classes': ('suit-tab suit-tab-basic',),
            'fields': ('preview', 'cover')
        }),
        (_('extra'), {
            'classes': ('suit-tab suit-tab-basic',),
            'fields': (
                           'response_time',
                       )
        }),
        (None, {
            'classes': ('suit-tab suit-tab-user-proposed',),
            'fields': ('notes',)
        }),
        (None, {
            'classes': ('suit-tab suit-tab-visibility',),
            'fields': ('is_featured', 'style')
        }),
        # (None, {
        #     'classes': ('suit-tab suit-tab-meta',),
        #     'fields': ('created_at', 'changed_at',)
        # }),
    )


class AddressForm(forms.ModelForm):
    class Meta:
        model = Area
        fields = ('title', 'parent')
        widgets = {
            'parent': AreaAutosuggestWidget,
        }

    def save(self, commit=True):
        from signali.utils import setting

        self.instance.size = setting('contact_address_areasize')
        return super().save(commit)


class OrganisationForm(forms.ModelForm):
    class Meta:
        model = Organisation
        exclude = []
        widgets = {
            'operational_area': AreaAutosuggestWidget,
        }


class OrganisationAdmin(ReverseModelAdmin):
    form = OrganisationForm
    inline_type = 'tabular'
    inline_reverse = (('address', AddressForm),)
    suit_form_includes = (
        ('admin/_area_contact_points.html', 'top', 'points'),
    )

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context["related_points"] = ContactPoint.objects.filter(parent=None, organisation_id=object_id)
        return super().change_view(request, object_id, form_url, extra_context)

    suit_form_tabs = (
        ('basic', _('basic')),
        ('visibility', _('visibility')),
        ('points', _('contact points')),
    )
    search_fields = ('title',)
    list_display = ('title', 'email', 'operational_area', 'is_public',)
    list_filter = (
        'is_public',
    )
    fieldsets = (
        (None, {
            'classes': ('suit-tab suit-tab-basic',),
            'fields': ('title', 'email', 'is_public', 'type', 'operational_area')
        }),
        (None, {
            'classes': ('suit-tab suit-tab-visibility',),
            'fields': ('popularity', 'views', 'is_featured', 'style')
        }),
    )



class ContactPointFeedbackAdmin(admin.ModelAdmin):
    suit_form_tabs = (
        ('basic', _('basic')),
    )

    list_per_page = 40
    list_display = ('user', 'contactpoint', 'rating', 'added_at', 'is_public',)
    list_editable = ('is_public', )
    list_filter = (
        ('user', admin.RelatedOnlyFieldListFilter),
        ('contactpoint', admin.RelatedOnlyFieldListFilter),
        'is_public',
    )
    search_fields = ('user', 'contactpoint', 'comment',)

    fieldsets = (
        (None, {
            'classes': ('suit-tab suit-tab-basic',),
            'fields': ('is_public', 'comment', 'user', 'rating', 'is_effective', 'is_easy',)
        }),
    )


admin.site.register(SignalContactPointFeedback, ContactPointFeedbackAdmin)
admin.site.register(ContactPointGrouped, ContactPointAdmin)
admin.site.register(ContactPoint)
admin.site.register(Organisation, OrganisationAdmin)
