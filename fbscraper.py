from __future__ import print_function
from facepy import GraphAPI
import facepy
import re
import json
from frontend import write_html
from dateutil.parser import parse

# You need to have the Access Token is stored in a plain text file ACCESS_TOKEN
# to get an access token follow this SO answer: http://stackoverflow.com/a/16054555/1780891
with open('./ACCESS_TOKEN', 'r') as file_handle:
    access_token = file_handle.readline().rstrip('\n')

graph = GraphAPI(access_token)


def get_comments(post_id):
    base_query = post_id + '/comments'

    # scrape the first page
    print('scraping:', base_query)
    comments = graph.get(base_query)
    data = comments['data']
    return data


def get_picture(post_id, dir="."):
    base_query = post_id + '?fields=object_id'
    try:
        pic_id = graph.get(base_query)['object_id']
    except KeyError:
        return None

    try:
        pic = graph.get('{}/picture'.format(pic_id))

        f_name = "{}/{}.png".format(dir, pic_id)
        f_handle = open(f_name, "wb")
        f_handle.write(pic)
        f_handle.close()
        return "{}.png".format(pic_id)
    except facepy.FacebookError:
        return None


def get_feed(page_id, pages=10):

    try:
        old_data = json.load(open('output/{}.json'.format(page_id), 'r'))
        last_post_time = parse(old_data[0]['created_time'])
    except FileNotFoundError:
        old_data = []
        last_post_time = parse("1000-01-01T12:05:06+0000")

    base_query = page_id + '/feed?limit=2'

    # scrape the first page
    print('scraping:', base_query)
    feed = graph.get(base_query)
    new_page_data = feed['data']

    is_new_post = (parse(new_page_data[0]['created_time']) > last_post_time)

    if is_new_post:
        data = new_page_data
    else:
        data = []

    # determine the next page
    next = feed['paging']['next']
    next_search = re.search('.*(\&until=[0-9]+)', next, re.IGNORECASE)
    if next_search:
        the_until_arg = next_search.group(1)

    pages = pages - 1

    # scrape the rest of the pages
    while (next is not False) and is_new_post and pages > 0:
        the_query = base_query + the_until_arg
        print('baking:', the_query)
        try:
            feed = graph.get(the_query)
            new_page_data = feed['data']
            is_new_post = (parse(new_page_data[0]['created_time']) > last_post_time)

            data.extend(new_page_data)
        except facepy.exceptions.OAuthError:
            print('start again at', the_query)
            break

        # determine the next page, until there isn't one
        try:
            next = feed['paging']['next']
            next_search = re.search('.*(\&until=[0-9]+)', next, re.IGNORECASE)
            if next_search:
                the_until_arg = next_search.group(1)
        except IndexError:
            print('last page...')
            next = False
        pages = pages - 1

    for post_dict in data:
        post_dict['pic'] = get_picture(post_dict['id'], dir='output')

    data.extend(old_data)

    data.sort(key=lambda x: parse(x['created_time']), reverse=True)

    json.dump(data, open('output/{}.json'.format(page_id), 'w'))

    return data


def get_aggregated_feed(pages):
    """
    Aggregates feeds give a list of pages and their ids.

    Input: A list of tuples
    Output: Combined list of posts sorted by timestamp
    """
    data = list()
    for page_name, _id in pages:
        page_data = get_feed(_id)
        for data_dict in page_data:
            data_dict['source'] = page_name
        data.extend(page_data)

    data.sort(key=lambda x: parse(x['created_time']), reverse=True)

    return data


if __name__ == "__main__":
    # Great thanks to https://gist.github.com/abelsonlive/4212647
    news_pages = [('The Scholar\'s Avenue', 'scholarsavenue'),
                  ('Awaaz IIT Kharagpur', 'awaaziitkgp'),
                  ('Technology Students Gymkhana', 'TSG.IITKharagpur'),
                  ('Technology IIT KGP', 'iitkgp.tech')]
    for_later = ['Cultural-IIT-Kharagpur']

    data = get_aggregated_feed(news_pages)

    json.dump(data, open('output/feed.json', 'w'))
    write_html(data, 'output/index.html')
