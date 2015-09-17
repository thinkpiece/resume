"""
Copyright (c) 2015 Junyoung Park

Publication Formatter from BibTex files
"""

import bibtexparser
import sys
import os
from operator import itemgetter
import re
# bibtex_database_entries


class PublicationFormatter:
    def __init__(self, publication_list):
        self.conference_list = self.__extract_conference(publication_list)
        self.journal_list = self.__extract_journal(publication_list)

    def __extract_conference(self, publication_list):
        conference_list = [paper for paper in publication_list
                           if paper['type'] == 'inproceedings']
        self.__refine_author_list(conference_list)
        return sorted(conference_list, key=itemgetter('year'), reverse=True)

    def __extract_journal(self, publication_list):
        journal_list = [paper for paper in publication_list
                        if paper['type'] == 'article']
        self.__refine_author_list(journal_list)
        return journal_list

    def __refine_author_list(self, paper_list):
        for paper in paper_list:
            authors = [name.strip() for name in paper['author'].split('and')]
            authors_refined = [self.__refine_author_name(name)
                               for name in authors]
            authors_str = ", ".join(name for name in authors_refined)
            paper['author'] = authors_str

    def __refine_author_name(self, name):
        """Emphasize my name."""
        if name == "Junyoung Park":
            name = "<u>Junyoung Park</u>"
        else:
            name = re.sub(r'([A-Z])[a-z]*([ -])', r'\1.\2', name)
        return name

    # TODO add more export methods for other formats such as TeX, markdown, ...
    def export_conference(self, output):
        for publication in self.conference_list:
            output.write("""
            <li>
              <dl>
                <dt>{title}</dt>
                <dd><em>{booktitle}</em>, {month}., {year}. <a href="{url}">\
<span class="glyphicon glyphicon-link"></span></a><br>
                  {authors}.
                </dd>
              </dl>
            </li>""".format(title=publication.get('title', '#empty#'),
                            booktitle=publication.get('booktitle', '#empty#'),
                            month=publication.get('month', '#empty#'),
                            year=publication.get('year', '#empty#'),
                            url=publication.get('bdsk-url-1', '#empty#'),
                            authors=publication.get('author', '#emtpy#')))


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("Usage: %s <filename>" % (argv[0],))
        return 1

    if not os.path.exists(argv[1]):
        sys.stderr.write("Error: File %r was not found" % (argv[1],))
        return 1

    with open(argv[1]) as bibtex_file:
        bibtex_database = bibtexparser.load(bibtex_file)

    publications = PublicationFormatter(bibtex_database.entries)
    export_html_file = open('html_output.html', 'w')
    publications.export_conference(export_html_file)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
