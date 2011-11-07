"""Calendar module for Gstudio templatetags"""
from datetime import date
from calendar import HTMLCalendar

from django.utils.dates import MONTHS
from django.utils.dates import WEEKDAYS_ABBR
from django.utils.formats import get_format
from django.core.urlresolvers import reverse

from gstudio.models import Objecttype

AMERICAN_TO_EUROPEAN_WEEK_DAYS = [6, 0, 1, 2, 3, 4, 5]


class GstudioCalendar(HTMLCalendar):
    """Override of HTMLCalendar"""

    def __init__(self):
        """Retrieve and convert the localized first week day
        at initialization"""
        HTMLCalendar.__init__(self, AMERICAN_TO_EUROPEAN_WEEK_DAYS[
            get_format('FIRST_DAY_OF_WEEK')])

    def formatday(self, day, weekday):
        """Return a day as a table cell with a link
        if objecttypes are published this day"""
        if day and day in self.day_objecttypes:
            day_date = date(self.current_year, self.current_month, day)
            archive_day_url = reverse('gstudio_objecttype_archive_day',
                                      args=[day_date.strftime('%Y'),
                                            day_date.strftime('%m'),
                                            day_date.strftime('%d')])
            return '<td class="%s objecttype"><a href="%s" '\
                   'rel="archives">%d</a></td>' % (
                self.cssclasses[weekday], archive_day_url, day)

        return super(GstudioCalendar, self).formatday(day, weekday)

    def formatmonth(self, theyear, themonth, withyear=True):
        """Return a formatted month as a table with
        new attributes computed for formatting a day"""
        self.current_year = theyear
        self.current_month = themonth
        self.day_objecttypes = [objecttypes.creation_date.day for objecttypes in
                            Objecttype.published.filter(
                                creation_date__year=theyear,
                                creation_date__month=themonth)]

        return super(GstudioCalendar, self).formatmonth(
            theyear, themonth, withyear)

    def formatweekday(self, day):
        """Return a weekday name translated
        as a table header."""
        return '<th class="%s">%s</th>' % (self.cssclasses[day],
                                           WEEKDAYS_ABBR[day].title())

    def formatmonthname(self, theyear, themonth, withyear=True):
        """Return a month name translated
        as a table row."""
        monthname = '%s %s' % (MONTHS[themonth].title(), theyear)
        return '<tr><th colspan="7" class="month">%s</th></tr>' % monthname
