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
from gstudio.models import Nodetype
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
                    help='All imported nodetypes belong to specified author'),
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
        self.import_nodetypes(feed.nodetypes)

    def import_nodetypes(self, feed_nodetypes):
        """Import nodetypes"""
        for feed_nodetype in feed_nodetypes:
            self.write_out('> %s... ' % feed_nodetype.title)
            creation_date = datetime(*feed_nodetype.date_parsed[:6])
            slug = slugify(feed_nodetype.title)[:255]

            if Nodetype.objects.filter(creation_date__year=creation_date.year,
                                    creation_date__month=creation_date.month,
                                    creation_date__day=creation_date.day,
                                    slug=slug):
                self.write_out(self.style.NOTICE(
                    'SKIPPED (already imported)\n'))
                continue

            metatypes = self.import_metatypes(feed_nodetype)
            nodetype_dict = {'title': feed_nodetype.title[:255],
                          'content': feed_nodetype.description,
                          'excerpt': feed_nodetype.get('summary'),
                          'status': PUBLISHED,
                          'creation_date': creation_date,
                          'start_publication': creation_date,
                          'last_update': datetime.now(),
                          'slug': slug}

            if not nodetype_dict['excerpt'] and self.auto_excerpt:
                nodetype_dict['excerpt'] = truncate_words(
                    strip_tags(feed_nodetype.description), 50)
            if self.metatype_tag:
                nodetype_dict['tags'] = self.import_tags(metatypes)

            nodetype = Nodetype(**nodetype_dict)
            nodetype.save()
            nodetype.metatypes.add(*metatypes)
            nodetype.sites.add(self.SITE)

            if self.default_author:
                nodetype.authors.add(self.default_author)
            elif feed_nodetype.get('author_detail'):
                try:
                    user = User.objects.create_user(
                        slugify(feed_nodetype.author_detail.get('name')),
                        feed_nodetype.author_detail.get('email', ''))
                except IntegrityError:
                    user = User.objects.get(
                        username=slugify(feed_nodetype.author_detail.get('name')))
                nodetype.authors.add(user)

            self.write_out(self.style.ITEM('OK\n'))

    def import_metatypes(self, feed_nodetype):
        metatypes = []
        for cat in feed_nodetype.get('tags', ''):
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
