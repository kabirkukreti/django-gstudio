"""Models of Objectapp"""
import warnings
from datetime import datetime

from django.db import models
from django.db.models import Q
from django.utils.html import strip_tags
from django.utils.html import linebreaks
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.db.models.signals import post_save
from django.utils.importlib import import_module
from django.contrib import comments
from django.contrib.comments.models import CommentFlag
from django.contrib.comments.moderation import moderator
from django.utils.translation import ugettext_lazy as _

from django.contrib.markup.templatetags.markup import markdown
from django.contrib.markup.templatetags.markup import textile
from django.contrib.markup.templatetags.markup import restructuredtext

import mptt
from tagging.fields import TagField

from gstudio.models import Objecttype
from gstudio.models import AbstractNode
from objectapp.settings import UPLOAD_TO
from objectapp.settings import MARKUP_LANGUAGE
from objectapp.settings import GBOBJECT_TEMPLATES
from objectapp.settings import GBOBJECT_BASE_MODEL
from objectapp.settings import MARKDOWN_EXTENSIONS
from objectapp.settings import AUTO_CLOSE_COMMENTS_AFTER
from objectapp.managers import gbobjects_published
from objectapp.managers import GBObjectPublishedManager
from objectapp.managers import AuthorPublishedManager
from objectapp.managers import DRAFT, HIDDEN, PUBLISHED
from objectapp.moderator import GBObjectCommentModerator
from objectapp.url_shortener import get_url_shortener
from objectapp.signals import ping_directories_handler
from objectapp.signals import ping_external_urls_handler
import reversion

class Author(User):
    """Proxy Model around User"""

    objects = models.Manager()
    published = AuthorPublishedManager()

    def gbobjects_published(self):
        """Return only the gbobjects published"""
        return gbobjects_published(self.gbobjects)

    @models.permalink
    def get_absolute_url(self):
        """Return author's URL"""
        return ('objectapp_author_detail', (self.username,))

    class Meta:
        """Author's Meta"""
        proxy = True

class GBObject(AbstractNode):
    """Model design publishing gbobjects"""
    STATUS_CHOICES = ((DRAFT, _('draft')),
                      (HIDDEN, _('hidden')),
                      (PUBLISHED, _('published')))

    content = models.TextField(_('content'))

    image = models.ImageField(_('image'), upload_to=UPLOAD_TO,
                              blank=True, help_text=_('used for illustration'))

    excerpt = models.TextField(_('excerpt'), blank=True,
                                help_text=_('optional element'))

    tags = TagField(_('tags'))
    objecttypes = models.ManyToManyField(Objecttype, verbose_name=_('objecttypes'),
                                        related_name='gbobjects',
                                        blank=True, null=True)
    related = models.ManyToManyField('self', verbose_name=_('related gbobjects'),
                                     blank=True, null=True)

    slug = models.SlugField(help_text=_('used for publication'),
                            unique_for_date='creation_date',
                            max_length=255)

    authors = models.ManyToManyField(User, verbose_name=_('authors'),
                                     related_name='gbobjects',
                                     blank=True, null=False)
    status = models.IntegerField(choices=STATUS_CHOICES, default=PUBLISHED)

    featured = models.BooleanField(_('featured'), default=False)
    comment_enabled = models.BooleanField(_('comment enabled'), default=True)
    pingback_enabled = models.BooleanField(_('linkback enabled'), default=True)

    creation_date = models.DateTimeField(_('creation date'),
                                         default=datetime.now)
    last_update = models.DateTimeField(_('last update'), default=datetime.now)
    start_publication = models.DateTimeField(_('start publication'),
                                             help_text=_('date start publish'),
                                             default=datetime.now)
    end_publication = models.DateTimeField(_('end publication'),
                                           help_text=_('date end publish'),
                                           default=datetime(2042, 3, 15))

    sites = models.ManyToManyField(Site, verbose_name=_('sites publication'),
                                   related_name='gbobjects')

    login_required = models.BooleanField(
        _('login required'), default=False,
        help_text=_('only authenticated users can view the gbobject'))
    password = models.CharField(
        _('password'), max_length=50, blank=True,
        help_text=_('protect the gbobject with a password'))

    template = models.CharField(
        _('template'), max_length=250,
        default='objectapp/gbobject_detail.html',
        choices=[('objectapp/gbobject_detail.html', _('Default template'))] + \
        GBOBJECT_TEMPLATES,
        help_text=_('template used to display the gbobject'))

    objects = models.Manager()
    published = GBObjectPublishedManager()


    @property
    def html_content(self):
        """Return the content correctly formatted"""
        if MARKUP_LANGUAGE == 'markdown':
            return markdown(self.content, MARKDOWN_EXTENSIONS)
        elif MARKUP_LANGUAGE == 'textile':
            return textile(self.content)
        elif MARKUP_LANGUAGE == 'restructuredtext':
            return restructuredtext(self.content)
        elif not '</p>' in self.content:
            return linebreaks(self.content)
        return self.content


    @property
    def previous_gbobject(self):
        """Return the previous gbobject"""
        gbobjects = GBObject.published.filter(
            creation_date__lt=self.creation_date)[:1]
        if gbobjects:
            return gbobjects[0]

    @property
    def next_gbobject(self):
        """Return the next gbobject"""
        gbobjects = GBObject.published.filter(
            creation_date__gt=self.creation_date).order_by('creation_date')[:1]
        if gbobjects:
            return gbobjects[0]

    @property
    def word_count(self):
        """Count the words of an gbobject"""
        return len(strip_tags(self.html_content).split())

    @property
    def is_actual(self):
        """Check if an gbobject is within publication period"""
        now = datetime.now()
        return now >= self.start_publication and now < self.end_publication

    @property
    def is_visible(self):
        """Check if an gbobject is visible on site"""
        return self.is_actual and self.status == PUBLISHED

    @property
    def related_published(self):
        """Return only related gbobjects published"""
        return gbobjects_published(self.related)

    @property
    def discussions(self):
        """Return published discussions"""
        return comments.get_model().objects.for_model(
            self).filter(is_public=True)

    @property
    def comments(self):
        """Return published comments"""
        return self.discussions.filter(Q(flags=None) | Q(
            flags__flag=CommentFlag.MODERATOR_APPROVAL))

    @property
    def pingbacks(self):
        """Return published pingbacks"""
        return self.discussions.filter(flags__flag='pingback')

    @property
    def trackbacks(self):
        """Return published trackbacks"""
        return self.discussions.filter(flags__flag='trackback')

    @property
    def comments_are_open(self):
        """Check if comments are open"""
        if AUTO_CLOSE_COMMENTS_AFTER and self.comment_enabled:
            return (datetime.now() - self.start_publication).days < \
                   AUTO_CLOSE_COMMENTS_AFTER
        return self.comment_enabled

    @property
    def short_url(self):
        """Return the gbobject's short url"""
        return get_url_shortener()(self)

    def __unicode__(self):
        return self.title

    @property
    def memberof_sentence(self):
        """Return the objecttype of which the gbobject is a member of"""
        
        if self.objecttypes.count:
            for each in self.objecttypes.all():
                return '%s is a member of objecttype %s' % (self.title, each)
        return '%s is not a fully defined name, consider making it a member of a suitable objecttype' % (self.title)


    @models.permalink
    def get_absolute_url(self):
        """Return gbobject's URL"""
        return ('objectapp_gbobject_detail', (), {
            'year': self.creation_date.strftime('%Y'),
            'month': self.creation_date.strftime('%m'),
            'day': self.creation_date.strftime('%d'),
            'slug': self.slug})

    class Meta:
        """GBObject's Meta"""
        ordering = ['-creation_date']
        verbose_name = _('object')
        verbose_name_plural = _('objects')
        permissions = (('can_view_all', 'Can view all'),
                       ('can_change_author', 'Can change author'), )


if not reversion.is_registered(GBObject):
    reversion.register(GBObject, follow=["objecttypes"])


moderator.register(GBObject, GBObjectCommentModerator)

mptt.register(GBObject, order_insertion_by=['title'])
post_save.connect(ping_directories_handler, sender=GBObject,
                  dispatch_uid='objectapp.gbobject.post_save.ping_directories')
post_save.connect(ping_external_urls_handler, sender=GBObject,
                  dispatch_uid='objectapp.gbobject.post_save.ping_external_urls')
