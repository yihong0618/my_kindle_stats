from http.cookies import SimpleCookie
from datetime import datetime
import re

import requests
import argparse

KINDLE_BASE_URL = "https://www.amazon.com/kindle/reading/insights/"
KINDLE_CN_BASE_URL = "https://www.amazon.cn/kindle/reading/insights/"

KINDLE_HISTORY_URL = KINDLE_BASE_URL + "data"
KINDLE_CN_HISTORY_URL = KINDLE_CN_BASE_URL + "data"

KINDLE_SINGLE_BOOK_URL = KINDLE_BASE_URL + "titlesCompleted/{book_id}?isPDoc=true"
KINDLE_CN_SINGLE_BOOK_URL = (
    KINDLE_CN_BASE_URL + "titlesCompleted/{book_id}?isPDoc={is_doc}"
)

AMAZON_BOOK_URL = "https://www.amazon.com/dp/{book_id}"
AMAZON_CN_BOOK_URL = "https://www.amazon.cn/dp/{book_id}"

KINDLE_HEADER = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/1AE148",
}

GITHUB_README_COMMENTS = (
    "(<!--START_SECTION:{name}-->\n)(.*)(<!--END_SECTION:{name}-->\n)"
)
KINDLE_HEAD_INFO = "## I have read {books_count} books this year\n\n"
KINDLE_TABLE_HEAD = "| ID | Title | Authors | Date | \n | ---- | ---- | ---- | ---- |\n"
KINDLE_STAT_TEMPLATE = "| {id} | {title} | {authors} | {date} |\n"


def replace_readme_comments(file_name, comment_str, comments_name):
    with open(file_name, "r+") as f:
        text = f.read()
        # regrex sub from github readme comments
        text = re.sub(
            GITHUB_README_COMMENTS.format(name=comments_name),
            r"\1{}\n\3".format(comment_str),
            text,
            flags=re.DOTALL,
        )
        f.seek(0)
        f.write(text)
        f.truncate()


class Kindle:
    def __init__(self, cookie, is_cn=True):
        self.kindle_cookie = cookie
        self.session = requests.Session()
        self.header = KINDLE_HEADER
        self.is_cn = is_cn
        self.KINDLE_URL = KINDLE_CN_HISTORY_URL if self.is_cn else KINDLE_HISTORY_URL
        self.KINDLE_BOOK_URL = (
            KINDLE_CN_SINGLE_BOOK_URL if self.is_cn else KINDLE_SINGLE_BOOK_URL
        )
        self.AMAZON_URL = AMAZON_CN_BOOK_URL if self.is_cn else AMAZON_BOOK_URL
        self.has_session = False
        self.csrf_token = ""

    def _parse_kindle_cookie(self):
        cookie = SimpleCookie()
        cookie.load(self.kindle_cookie)
        cookies_dict = {}
        cookiejar = None
        for key, morsel in cookie.items():
            cookies_dict[key] = morsel.value
            cookiejar = requests.utils.cookiejar_from_dict(
                cookies_dict, cookiejar=None, overwrite=True
            )
        return cookiejar

    def make_session(self):

        cookies = self._parse_kindle_cookie()
        if not cookies:
            raise Exception("Please make sure your amazon cookie is right")
        self.session.cookies = cookies
        self.has_session = True

    def get_kindle_read_data(self):
        if not self.has_session:
            self.make_session()
        r = self.session.get(self.KINDLE_URL, headers=self.header)
        return r.json()

    def get_single_read_book_info(self, book_id, is_doc):
        # format True -> true False -> false
        is_doc = ["false", "true"][is_doc]
        url = self.KINDLE_BOOK_URL.format(book_id=book_id, is_doc=is_doc)
        book_info = self.session.get(url, headers=self.header).json()
        if not book_info:
            print(f"There's no book info if id {book_id}")
        book_title = book_info["title"]
        slice_index = book_title.find("(")
        if slice_index == -1:
            slice_index = book_title.find("（")
        if slice_index != -1:
            book_title = book_title[:slice_index]
        book_title = book_title.replace(" ", "")
        if is_doc == "false":
            book_url = self.AMAZON_URL.format(book_id=book_id)
            book_title = f"[{book_title}]({book_url})"
        book_authors = book_info.get("authors")
        if len(book_authors) > 2:
            book_authors = ",".join(book_authors[:2]) + "..."
        else:
            book_authors = ",".join(book_authors) if book_authors else ""
        return book_title, book_authors

    def make_all_books_list(self):
        year = datetime.now().year
        self.make_session()
        year_books_info = self.get_kindle_read_data()
        titles_read = year_books_info.get("goal_info", {}).get("titles_read")
        if not titles_read:
            return
        result = []
        for title in titles_read:
            if int(title.get("date_read", "1926-08-17")[:4]) < year:
                break
            is_doc = title.get("content_type", "") == "PDOC"
            book_title, authors = self.get_single_read_book_info(
                title.get("asin"), is_doc
            )
            if not book_title:
                continue
            title["book_title"] = book_title
            title["authors"] = authors
            result.append(title)
        return result

    def make_kindle_string(self, book_list):
        books_count = len(book_list)
        s = KINDLE_HEAD_INFO.format(books_count=books_count)
        s += KINDLE_TABLE_HEAD
        index = 1
        for book in book_list:
            year = datetime.now().year
            s += KINDLE_STAT_TEMPLATE.format(
                id=str(index),
                title=book.get("book_title"),
                authors=book.get("authors"),
                date=str(book.get("date_read"))[:10],  # only keep date
            )
            index += 1
        return s


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("cookie", help="amazon or amazon cn cookie")
    parser.add_argument(
        "--is-cn",
        dest="is_cn",
        action="store_true",
        help="if amazon accout is cn",
    )
    options = parser.parse_args()
    kindle = Kindle(options.cookie, options.is_cn)
    book_list = kindle.make_all_books_list()
    s = kindle.make_kindle_string(book_list)
    replace_readme_comments("README.md", s, "my_kindle")
