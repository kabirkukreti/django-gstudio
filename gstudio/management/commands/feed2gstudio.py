"""Feed to Gstudio command module"""
import sys
from datetime import datetime
from optparse import make_option

from django.utils.html import strip_tags
from django.db.utils import IntegrityError
from django.utils.encoding import smart_str
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.utils.text import truncate_words
from django.template.defaultfilters import slugify
from django.core.management.base import CommandError
from django.core.management.base import LabelCommand

from gstudio import __version__
from gstudio.models import Objecttype
from gstudio.models import Metatype
from gstudio.managers import PUBLISHED
from gstudio.signals import disconnect_gstudio_signals


class Command(LabelCommand):
    """Command object for importing a RSS or Atom
    feed into Gstudio."""
    help = 'Import a RSS or Atom feed into Gstudio.'
    label = 'feed url'
    args = 'url'

    option_list = LabelCommand.option_list + (
        make_option('--noautoexcerpt', action='store_false',
                    dest='auto_excerpt', default=True,
                    help='Do NOT generate an excerpt if not present.'),
        make_option('--author', dest='author', default='',
                    help='All imported objecttypes belong to specified author'),
        make_option('--metatype-is-tag', action='store_true',
                    dest='metatype-tag', default=False,
                    help='Store metatypes as tags'),
        )
    SITE = Site.objects.get_current()

    def __init__(self):
        """Init the Command and add custom styles"""
        super(Command, self).__init__()
        self.style.TITLE = self.style.SQL_FIELD
        self.style.STEP = self.style.SQL_COLTYPE
        self.style.ITEM = self.style.HTTP_INFO
        disconnect_gstudio_signals()

    def write_out(self, message, verbosity_level=1):
        """Convenient method for outputing"""
        if self.verbosity and self.verbosity >= verbosity_level:
            sys.stdout.write(smart_str(message))
            sys.stdout.flush()

    def handle_label(self, url, **options):
        try:
            import feedparser
        except ImportError:
            raise CommandError('You need to install the feedparser ' \
                               'module to run this command.')

        self.verbosity = int(options.get('verbosity', 1))
        self.auto_excerpt = options.get('auto_excerpt', True)
        self.default_author = options.get('author')
        self.metatype_tag = options.get('metatype-tag', False)
        if self.default_author:
            try:
                self.default_author = User.objects.get(
                    username=self.default_author)
            except User.DoesNotExist:
                raise CommandError('Invalid username for default author')

        self.write_out(self.style.TITLE(
            'Starting importation of %s to Gstudio %s:\n' % (url, __version__)))

        feed = feedparser.parse(url)
        self.import_objecttypes(feed.objecttypes)

    def import_objecttypes(self, feed_objecttypes):
        """Import objecttypes"""
        for feed_objecttype in feed_objecttypes:
            self.write_out('> %s... ' % feed_objecttype.title)
            creation_date = datetime(*feed_objecttype.date_parsed[:6])
            slug = slugify(feed_objecttype.title)[:255]

            if Objecttype.objects.filter(creation_date__year=creation_date.year,
                                    creation_date__month=creation_date.month,
                                    creation_date__day=creation_date.day,
                                    slug=slug):
                self.write_out(self.style.NOTICE(
                    'SKIPPED (already imported)\n'))
                continue

            metatypes = self.import_metatypes(feed_objecttype)
            objecttype_dict = {'title': feed_objecttype.title[:255],
                          'content': feed_objecttype.description,
                          'excerpt': feed_objecttype.get('summary'),
                          'status': PUBLISHED,
                          'creation_date': creation_date,
                          'start_publication': creation_date,
                          'last_update': datetime.now(),
                          'slug': slug}

            if not objecttype_dict['excerpt'] and self.auto_excerpt:
                objecttype_dict['excerpt'] = truncate_words(
                    strip_tags(feed_objecttype.description), 50)
            if self.metatype_tag:
                objecttype_dict['tags'] = self.import_tags(metatypes)

            objecttype = Objecttype(**objecttype_dict)
            objecttype.save()
            objecttype.metatypes.add(*metatypes)
            objecttype.sites.add(self.SITE)

            if self.default_author:
                objecttype.authors.add(self.default_author)
            elif feed_objecttype.get('author_detail'):
                try:
                    user = User.objects.create_user(
                        slugify(feed_objecttype.author_detail.get('name')),
                        feed_objecttype.author_detail.get('email', ''))
                except IntegrityError:
                    user = User.objects.get(
                        username=slugify(feed_objecttype.author_detail.get('name')))
                objecttype.authors.add(user)

            self.write_out(self.style.ITEM('OK\n'))

    def import_metatypes(self, feed_objecttype):
        metatypes = []
        for cat in feed_objecttype.get('tags', ''):
            metatype, created = Metatype.objects.get_or_create(
                slug=slugify(cat.term), defaults={'title': cat.term})
            metatypes.append(metatype)
        return metatypes

    def import_tags(self, metatypes):
        tags = []
        for cat in metatypes:
            if len(cat.title.split()) > 1:
                tags.append('"%s"' % slugify(cat.title).replace('-', ' '))
            else:
                tags.append(slugify(cat.title).replace('-', ' '))
        return ', '.join(tags)
