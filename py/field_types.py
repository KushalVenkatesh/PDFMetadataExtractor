import re
from sqlalchemy import Integer, String, Float, Boolean, Date
from dateutil.parser import parse
from datetime import date, datetime
from fuzzywuzzy import fuzz

def get_handler(type):
    classes = {'human_name' : HumanNameHandler,
               'date' : DateHandler,
               'proper_noun' : ProperNounHandler
               }
    return classes[type]()

class TypeHandler(object):
    def format(self, value):
        pass
    def patterns(self):
        return self._patterns
    def col_type(self):
        return self._col_type
    def format(self, value):
        return value
    def preprocess(self, text):
        return text
    def find_value(self, text):
        for pattern in self.patterns():
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()
        return None

    def match_score(self, query, text):
        return int(query in text)

    def compare(self, value1, value2):
        return value1 == value2


class HumanNameHandler(TypeHandler):
    _col_type = String(255)
    _patterns = [r"[A-Za-z01\-\s,'.]+"]

    def format(self, value):
        value = re.sub(r'\s+', ' ', value)
        result = re.search(r"([A-Za-z01\-\s']+),\s*([A-Za-z01\-\s']+.)", value)
        try:
            name = "%s %s" % (result.group(2), result.group(1))
        except AttributeError:
            # Maybe it's a name in "Firstname Lastname" format
            name = value

        if name.isupper():
            return name.title()
        else:
            return name

    def match_score(self, query, text):
        try:
            query = query.translate(None, ",.")
            words = query.split()
            scores = [(fuzz.partial_ratio(word, text), len(word))
                      for word in words if len(word) > 1]
            return sum([a[0] * a[1] for a in scores]
                       ) / (100 * float(sum([a[1] for a in scores])))
        except Exception:
            return 0

    def compare(self, value1, value2):
        return (self.match_score(value1, value2) + self.match_score(value2, value1)) / 2


class DateHandler(TypeHandler):
    _patterns = [r"[\dIloO]{1,2}[/1Il-][\dIloO]{1,2}[/1Il-][\dIloO]{4}",
                 r"[\dIloO]{4}-[\dIloO]{2}-[\dIloO]{2}",
                 r"[\dIloO]{1,2}[/Il1-][\dIloO]{1,2}[/Il1-][\dIloO]{2}\b",
                 r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*[\d]{1,2}\s*\d{4}"
                 ]
    _col_type = Date

    def format(self, value):
        replacements = [[(r"([\doOIl]{1,2})[/I1l-]([\doOIl]{1,2})[/I1l-]([\doOIl]{4})", r"\1/\2/\3"),
                         (r"[Il]", "1"), (r"[oO]", "0")],
                        [(r"[Il]", "1"), (r"[oO]", "0")],
                        [(r"([\doOIl]{1,2})[/Il1-]([\doOIl]{1,2})[/Il1-]([\doOIl]{2})", r"\1/\2/\3"),
                         (r"[Il]", "1"), (r"[oO]", "0")],
                        []
                        ]
        for p, r in zip(self.patterns(), replacements):
            try:
                result = re.search(p, value)
                if result:
                    new_value = result.group(0)
                    for error, correction in r:
                        new_value = re.sub(error, correction, new_value)
                    d=parse(new_value).date()
                    # TODO: leave option for future years
                    if d.year > date.today().year:
                        d=date(year=d.year-100, month=d.month, day=d.day)
                    return d
            except ValueError:
                pass
        return None

    def preprocess(self, value):
        # Get rid of extra spacing
        if not re.search(r"[A-Z][a-z]{2}", value):
            value = re.sub(r"\s+", "", value)
        # Get rid of punctuation noise from scanning
        return str(value).translate(None, r",.'`")

    def match_score(self, query, text):
        formats = ["%m/%d/%Y", "%m/%d/%y", "%b %d, %Y"]
        strings = [query.strftime(f) for f in formats]
        return max([fuzz.partial_ratio(q, text) for q in strings]) / 100.



class ProperNounHandler(TypeHandler):
    _col_type = String(1023)
    _patterns = [r".+"]

    def format(self, value):
        return value.title()
