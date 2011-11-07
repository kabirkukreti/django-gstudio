"""Test cases for Gstudio's sitemaps"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.sites.models import Site

from tagging.models import Tag

from gstudio.models import Objecttype
from gstudio.models import Author
from gstudio.models import Metatype
from gstudio.managers import PUBLISHED
from gstudio.sitemaps import ObjecttypeSitemap
from gstudio.sitemaps import MetatypeSitemap
from gstudio.sitemaps import AuthorSitemap
from gstudio.sitemaps import TagSitemap


class GstudioSitemapsTestCase(TestCase):
    """Test cases for Sitemaps classes provided"""
    urls = 'gstudio.tests.urls'

    def setUp(self):
        self.site = Site.objects.get_current()
        self.author = User.objects.create(username='admin',
                                          email='admin@example.com')
        self.metatype = Metatype.objects.create(title='Tests', slug='tests')
        params = {'title': 'My objecttype 1', 'content': 'My content 1',
                  'tags': 'gstudio, test', 'slug': 'my-objecttype-1',
                  'status': PUBLISHED}
        self.objecttype_1 = Objecttype.objects.create(**params)
        self.objecttype_1.authors.add(self.author)
        self.objecttype_1.metatypes.add(self.metatype)
        self.objecttype_1.sites.add(self.site)

        params = {'title': 'My objecttype 2', 'content': 'My content 2',
                  'tags': 'gstudio', 'slug': 'my-objecttype-2',
                  'status': PUBLISHED}
        self.objecttype_2 = Objecttype.objects.create(**params)
        self.objecttype_2.authors.add(self.author)
        self.objecttype_2.metatypes.add(self.metatype)
        self.objecttype_2.sites.add(self.site)

    def test_objecttype_sitemap(self):
        sitemap = ObjecttypeSitemap()
        self.assertEquals(len(sitemap.items()), 2)
        self.assertEquals(sitemap.lastmod(self.objecttype_1),
                          self.objecttype_1.last_update)

    def test_metatype_sitemap(self):
        sitemap = MetatypeSitemap()
        self.assertEquals(len(sitemap.items()), 1)
        self.assertEquals(sitemap.lastmod(self.metatype),
                          self.objecttype_2.creation_date)
        self.assertEquals(sitemap.lastmod(Metatype.objects.create(
            title='New', slug='new')), None)
        self.assertEquals(sitemap.priority(self.metatype), '1.0')

    def test_author_sitemap(self):
        sitemap = AuthorSitemap()
        authors = sitemap.items()
        self.assertEquals(len(authors), 1)
        self.assertEquals(sitemap.lastmod(authors[0]),
                          self.objecttype_2.creation_date)
        self.assertEquals(sitemap.lastmod(Author.objects.create(
            username='New', email='new@example.com')), None)
        self.assertEquals(sitemap.location(self.author), '/authors/admin/')

    def test_tag_sitemap(self):
        sitemap = TagSitemap()
        gstudio_tag = Tag.objects.get(name='gstudio')
        self.assertEquals(len(sitemap.items()), 2)
        self.assertEquals(sitemap.lastmod(gstudio_tag),
                          self.objecttype_2.creation_date)
        self.assertEquals(sitemap.priority(gstudio_tag), '1.0')
        self.assertEquals(sitemap.location(gstudio_tag), '/tags/gstudio/')

    def test_metatype_sitemap_zero_division_error(self):
        Objecttype.objects.all().delete()
        metatype_sitemap = MetatypeSitemap()
        metatype_sitemap.items()
        self.assertEquals(metatype_sitemap.priority(self.metatype), '0.5')
