"""Test cases for Gstudio's managers"""
from datetime import datetime

from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.sites.models import Site

from tagging.models import Tag

from gstudio.models import Nodetype
from gstudio.models import Author
from gstudio.models import Metatype
from gstudio.managers import PUBLISHED
from gstudio.managers import tags_published
from gstudio.managers import nodetypes_published


class ManagersTestCase(TestCase):

    def setUp(self):
        self.sites = [
            Site.objects.get_current(),
            Site.objects.create(domain='http://domain.com',
                                name='Domain.com')]
        self.authors = [
            User.objects.create_user(username='webmaster',
                                     email='webmaster@example.com'),
            User.objects.create_user(username='contributor',
                                     email='contributor@example.com')]
        self.metatypes = [
            Metatype.objects.create(title='Metatype 1',
                                    slug='metatype-1'),
            Metatype.objects.create(title='Metatype 2',
                                    slug='metatype-2')]

        params = {'title': 'My nodetype 1', 'content': 'My content 1',
                  'tags': 'gstudio, test', 'slug': 'my-nodetype-1',
                  'status': PUBLISHED}
        self.nodetype_1 = Nodetype.objects.create(**params)
        self.nodetype_1.authors.add(self.authors[0])
        self.nodetype_1.metatypes.add(*self.metatypes)
        self.nodetype_1.sites.add(*self.sites)

        params = {'title': 'My nodetype 2', 'content': 'My content 2',
                  'tags': 'gstudio, test', 'slug': 'my-nodetype-2'}
        self.nodetype_2 = Nodetype.objects.create(**params)
        self.nodetype_2.authors.add(*self.authors)
        self.nodetype_2.metatypes.add(self.metatypes[0])
        self.nodetype_2.sites.add(self.sites[0])

    def test_tags_published(self):
        self.assertEquals(tags_published().count(), Tag.objects.count())
        Tag.objects.create(name='out')
        self.assertNotEquals(tags_published().count(), Tag.objects.count())

    def test_author_published_manager_get_query_set(self):
        self.assertEquals(Author.published.count(), 1)
        self.nodetype_2.status = PUBLISHED
        self.nodetype_2.save()
        self.assertEquals(Author.published.count(), 2)
        self.nodetype_2.sites.remove(self.sites[0])
        self.nodetype_2.sites.add(self.sites[1])
        self.assertEquals(Author.published.count(), 1)

    def test_nodetypes_published(self):
        self.assertEquals(nodetypes_published(Nodetype.objects.all()).count(), 1)
        self.nodetype_2.status = PUBLISHED
        self.nodetype_2.save()
        self.assertEquals(nodetypes_published(Nodetype.objects.all()).count(), 2)
        self.nodetype_1.sites.clear()
        self.assertEquals(nodetypes_published(Nodetype.objects.all()).count(), 1)
        self.nodetype_1.sites.add(*self.sites)
        self.nodetype_1.start_publication = datetime(2020, 1, 1)
        self.nodetype_1.save()
        self.assertEquals(nodetypes_published(Nodetype.objects.all()).count(), 1)
        self.nodetype_1.start_publication = datetime(2000, 1, 1)
        self.nodetype_1.save()
        self.assertEquals(nodetypes_published(Nodetype.objects.all()).count(), 2)
        self.nodetype_1.end_publication = datetime(2000, 1, 1)
        self.nodetype_1.save()
        self.assertEquals(nodetypes_published(Nodetype.objects.all()).count(), 1)
        self.nodetype_1.end_publication = datetime(2020, 1, 1)
        self.nodetype_1.save()
        self.assertEquals(nodetypes_published(Nodetype.objects.all()).count(), 2)

    def test_nodetype_published_manager_get_query_set(self):
        self.assertEquals(Nodetype.published.count(), 1)
        self.nodetype_2.status = PUBLISHED
        self.nodetype_2.save()
        self.assertEquals(Nodetype.published.count(), 2)
        self.nodetype_1.sites.clear()
        self.assertEquals(Nodetype.published.count(), 1)
        self.nodetype_1.sites.add(*self.sites)
        self.nodetype_1.start_publication = datetime(2020, 1, 1)
        self.nodetype_1.save()
        self.assertEquals(Nodetype.published.count(), 1)
        self.nodetype_1.start_publication = datetime(2000, 1, 1)
        self.nodetype_1.save()
        self.assertEquals(Nodetype.published.count(), 2)
        self.nodetype_1.end_publication = datetime(2000, 1, 1)
        self.nodetype_1.save()
        self.assertEquals(Nodetype.published.count(), 1)
        self.nodetype_1.end_publication = datetime(2020, 1, 1)
        self.nodetype_1.save()
        self.assertEquals(Nodetype.published.count(), 2)

    def test_nodetype_published_manager_on_site(self):
        self.assertEquals(Nodetype.published.on_site().count(), 2)
        self.nodetype_2.sites.clear()
        self.nodetype_2.sites.add(self.sites[1])
        self.assertEquals(Nodetype.published.on_site().count(), 1)
        self.nodetype_1.sites.clear()
        self.assertEquals(Nodetype.published.on_site().count(), 0)

    def test_nodetype_published_manager_basic_search(self):
        self.assertEquals(Nodetype.published.basic_search('My ').count(), 1)
        self.nodetype_2.status = PUBLISHED
        self.nodetype_2.save()
        self.assertEquals(Nodetype.published.basic_search('My ').count(), 2)
        self.assertEquals(Nodetype.published.basic_search('1').count(), 1)
        self.assertEquals(Nodetype.published.basic_search('content 1').count(), 2)

    def test_nodetype_published_manager_advanced_search(self):
        metatype = Metatype.objects.create(
            title='SimpleMetatype', slug='simple')
        self.nodetype_2.metatypes.add(metatype)
        self.nodetype_2.tags = self.nodetype_2.tags + ', custom'
        self.nodetype_2.status = PUBLISHED
        self.nodetype_2.save()
        self.assertEquals(
            Nodetype.published.advanced_search('content').count(), 2)
        search = Nodetype.published.advanced_search('content 1')
        self.assertEquals(search.count(), 1)
        self.assertEquals(search.all()[0], self.nodetype_1)
        self.assertEquals(
            Nodetype.published.advanced_search('content 1 or 2').count(), 2)
        self.assertEquals(
            Nodetype.published.advanced_search('content 1 and 2').count(), 0)
        self.assertEquals(
            Nodetype.published.advanced_search('content 1 2').count(), 0)
        self.assertEquals(
            Nodetype.published.advanced_search('"My content" 1 or 2').count(), 2)
        self.assertEquals(
            Nodetype.published.advanced_search('-"My content" 2').count(), 0)
        search = Nodetype.published.advanced_search('content -1')
        self.assertEquals(search.count(), 1)
        self.assertEquals(search.all()[0], self.nodetype_2)
        self.assertEquals(Nodetype.published.advanced_search(
            'content metatype:SimpleMetatype').count(), 1)
        self.assertEquals(Nodetype.published.advanced_search(
            'content metatype:simple').count(), 1)
        self.assertEquals(Nodetype.published.advanced_search(
            'content metatype:"Metatype 1"').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            'content metatype:"metatype-1"').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            'content metatype:"metatype-2"').count(), 1)
        self.assertEquals(Nodetype.published.advanced_search(
            'content tag:gstudio').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            'content tag:custom').count(), 1)
        self.assertEquals(Nodetype.published.advanced_search(
            'content author:webmaster').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            'content author:contributor').count(), 1)
        self.assertEquals(Nodetype.published.advanced_search(
            'content author:webmaster tag:gstudio').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            'content author:webmaster tag:custom').count(), 1)
        self.assertEquals(Nodetype.published.advanced_search(
            'content 1 or 2 author:webmaster').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            'content 1 or 2 author:webmaster').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            '(author:webmaster content) my').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            '(author:webmaster) or (author:contributor)').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            '(author:webmaster) (author:contributor)').count(), 0)
        self.assertEquals(Nodetype.published.advanced_search(
            '(author:webmaster content) 1').count(), 1)
        self.assertEquals(Nodetype.published.advanced_search(
            '(author:webmaster content) or 2').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            '(author:contributor content) or 1').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            '(author:contributor content) or 2').count(), 1)
        self.assertEquals(Nodetype.published.advanced_search(
            '(author:webmaster or ("hello world")) and 2').count(), 1)

        # Complex queries
        self.assertEquals(Nodetype.published.advanced_search(
            '(author:admin and "content 1") or author:webmaster').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            'author:admin and ("content 1" or author:webmaster)').count(), 0)
        self.assertEquals(Nodetype.published.advanced_search(
            'author:admin and "content 1" or author:webmaster').count(), 0)
        self.assertEquals(Nodetype.published.advanced_search(
            '-(author:webmaster and "content 1")').count(), 1)
        self.assertEquals(Nodetype.published.advanced_search(
            '-(-author:webmaster and "content 1")').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            'metatype:"metatype -1" or author:"web master"').count(), 0)
        self.assertEquals(Nodetype.published.advanced_search(
            'metatype:"metatype-1" or author:"webmaster"').count(), 2)

        # Wildcards
        self.assertEquals(Nodetype.published.advanced_search(
            'author:webm*').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            'author:*bmas*').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            'author:*master').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            'author:*master metatype:*ory-2').count(), 1)
        self.assertEquals(Nodetype.published.advanced_search(
            'author:*master or metatype:cate*').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            'metatype:*ate*').count(), 2)
        self.assertEquals(Nodetype.published.advanced_search(
            'author:"webmast*"').count(), 0)
        self.assertEquals(Nodetype.published.advanced_search(
            'tag:"gstudio*"').count(), 0)
        self.assertEquals(Nodetype.published.advanced_search(
            'tag:*inni*').count(), 2)

    def test_nodetype_published_manager_advanced_search_with_punctuation(self):
        self.nodetype_2.content = 'How are you today ? Fine thank you ! OK.'
        self.nodetype_2.status = PUBLISHED
        self.nodetype_2.save()
        self.assertEquals(Nodetype.published.advanced_search(
            'today ?').count(), 1)
        self.assertEquals(Nodetype.published.advanced_search(
            'today or ! or .').count(), 1)
        self.assertEquals(Nodetype.published.advanced_search(
            '"you today ?"').count(), 1)

    def test_nodetype_published_manager_search(self):
        self.nodetype_2.content = self.nodetype_2.content + ' * '
        self.nodetype_2.status = PUBLISHED
        self.nodetype_2.save()
        # Be sure that basic_search does not return
        # the same results of advanced_search
        self.assertNotEquals(
            Nodetype.published.basic_search('content 1').count(),
            Nodetype.published.advanced_search('content 1').count())
        # Now check the fallback with the '*' pattern
        # which will fails advanced search
        self.assertEquals(Nodetype.published.search('*').count(), 1)
