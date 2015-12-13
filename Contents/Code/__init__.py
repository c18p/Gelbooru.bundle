NAME = 'Gelbooru'
PREFIX  = '/photos/gelbooru'
ICON  = "icon-default.png"
LOGIN_URL  = '{server}/index.php?page=account&s=login&code=00'
SEARCH_URL = '{server}/index.php?page=dapi&s=post&q=index&tags={tags}&limit={limit}&pid={page}&cid={time}'
SEARCH_HISTORY_KEY = 'search_history' # {query: thumbnail}
TIME_KEY = 'start_time'
PAGE_THUMBS = 'page_thumbs' # {hash(tags,limit,page,time): thumbnail}
DAY_IN_SECONDS = 86400
# the date options to prompt the client with, excluding 'all time' which is always there
DATE_VIEWS = [1, 7, 30, 90, 180, 365]
# list of tags to force onto every query
FORCED_TAGS = ['-animated']
# sorting methods to prompt the client with. sort:score is broken on rule34.xxx
SORT_TAGS = ['sort:score:desc', 'sort:score:asc', 'sort:updated:desc', 'sort:updated:asc']
PAGE_LIMIT = 20 # limit for paging of pages
             
def Start():
    ObjectContainer.title1 = NAME
    HTTP.CacheTime = CACHE_1MONTH
    HTTP.User_Agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/33.0.1750.152 Safari/537.36'
    Plugin.AddViewGroup("Details", viewMode="InfoList", mediaType="items")
    Plugin.AddViewGroup("Images",  viewMode="Pictures", mediaType="items")
    if SEARCH_HISTORY_KEY not in Dict:
        Dict[SEARCH_HISTORY_KEY] = {}
    if PAGE_THUMBS not in Dict:
        Dict[PAGE_THUMBS] = {}
    if 'cookie-%s'%Prefs['server'] not in Dict:
        Dict['cookie-%s'%Prefs['server']] = None
    Dict[TIME_KEY] = int(Datetime.TimestampFromDatetime(Datetime.Now()))
    Dict.Save()


@handler(PREFIX, NAME)
def MainMenu():       
    oc = ObjectContainer()
    if Dict['cookie-%s'%Prefs['server']] is not None:
        oc.add(GetPhotoAlbum(title=L('latest'), query=ProcessQuery(None)))
        oc.add(InputDirectoryObject(key=Callback(Search), title=L('newsearch')))
        oc.add(DirectoryObject(key=Callback(ListSearchHistory, action="view"), title=L('savedsearch')))
        oc.add(DirectoryObject(key=Callback(SearchManagerMenu), title=L('managesearches')))
        oc.add(DirectoryObject(key=Callback(Logout), title=L('logout')))
    else:
        oc.add(DirectoryObject(key=Callback(Login), title=L('login')))
    oc.add(PrefsObject(title=L('preferences')))
    return oc


@route(PREFIX + '/login')
def Login():
    if not Prefs['username'] or not Prefs['password']:
        ErrorMessage(error="Login", message="Username or password is blank. Check settings.")
    payload = {'user': Prefs['username'].strip(),
               'pass': Prefs['password'].strip(),
               'submit': 'Log in'}
    headers = {'user-agent': HTTP.User_Agent,
               'origin': Prefs['server'],
               'referer': Prefs['server'] + '/index.php?page=account&s=login&code=00',
               'content-type': 'application/x-www-form-urlencoded'}
    try:
        r = HTTP.Request(url=LOGIN_URL.format(server=Prefs['server']), headers=headers,
                         values=payload, immediate=True, cacheTime=0)
        cookies = HTTP.CookiesForURL(LOGIN_URL.format(server=Prefs['server']))
        Dict['cookie-%s'%Prefs['server']] = cookies
        Dict.Save()
        Log(Dict['cookie-%s'%Prefs['server']])
    except:
        return ErrorMessage(error="Login", message="Login Error. Try Again Later")
    return ErrorMessage(error="Login", message="Login Success.")


@route(PREFIX + '/logout')
def Logout():
    Dict['cookie-%s'%Prefs['server']] = None
    return ErrorMessage("Logout", "Success")


def ErrorMessage(error, message):
    return ObjectContainer(header=unicode(error), message=unicode(message))


# make a limit=1 request to grab a thumbnail to use for a query
def GetThumbnail(query, time=0):
    url = SEARCH_URL.format(server=Prefs['server'], tags=query.strip(), limit=1, page=0, time=time)
    try:
        post = XML.ElementFromURL(url).xpath("//post")[0]
        thumb_url = post.get('preview_url')
    except:
        thumb_url = ""
    return thumb_url    


# add tags from settings to query
def ProcessQuery(query):
    if query is None:
        query = ""
    # add rating tag if set in prefs
    if Prefs['rating'] != "all":
        query += " {0}".format(Prefs['rating'])
    if Prefs['globals_enabled']:
        # Global remove tags
        if Prefs['remove_tags']:
            remove_tags = Prefs['remove_tags'].split()
            for tag in remove_tags:
                query += " -{0}".format(tag)
        # Global add tags
        if Prefs['add_tags']:
            add_tags = Prefs['add_tags'].split()
            for tag in add_tags:
                query += " {0}".format(tag)
    # Forced tags (hardcoded for compatibility reasons)
    for tag in FORCED_TAGS:
        query += " {0}".format(tag)
    if Prefs['threshold_enabled']:
        # Global score threshold
        # see if it makes sense to add the threshold
        tags = query.split()
        score = False
        for tag in tags:
            if tag.startswith("score:"):
                score = True
                break
        if 'sort:score:desc' in tags:
            score = True
        # add it
        if not score:
            query += " score:>{0}".format(Prefs['score_threshold']) if Prefs['score_threshold'] != "0" else ""
    return query


@route(PREFIX + '/search/history/manage')
def SearchManagerMenu():
    oc = ObjectContainer(no_cache=True, no_history=True)
    oc.add(DirectoryObject(key=Callback(ListSearchHistory, action="remove"),
                           title=L('searchhistoryremove')))
    oc.add(DirectoryObject(key=Callback(ClearSearchHistory), title=L('searchhistoryclear')))
    return oc


@route(PREFIX + '/search/history/list/{action}')
def ListSearchHistory(action):
    oc = ObjectContainer()
    for item, thumb in Dict[SEARCH_HISTORY_KEY].iteritems():
        if action == "remove":
            oc.add(DirectoryObject(key=Callback(SearchHistoryRemoveItem, item=item),
                                   title="{0}: {1}".format(L('remove'), item),
                                   thumb=Resource.ContentsOfURLWithFallback(thumb,
                                                                            fallback=R(ICON))))
        elif action == "view":
            oc.add(DirectoryObject(key=Callback(Search, query=item), title=item,
                                   thumb=Resource.ContentsOfURLWithFallback(thumb,
                                                                            fallback=R(ICON))))
    return oc


@route(PREFIX + '/search/history/clear')
def ClearSearchHistory():
    Dict[SEARCH_HISTORY_KEY] = {}
    Dict.Save()


@route(PREFIX + '/search/history/remove/{item}')
def SearchHistoryRemoveItem(item):
    oc = ObjectContainer()
    if item not in Dict[SEARCH_HISTORY_KEY]:
        return ErrorMessage(item, "not in search history")
    del Dict[SEARCH_HISTORY_KEY][item]
    Dict.Save()
    return ErrorMessage(item, "removed from history")


@route(PREFIX + '/search')
def Search(query):
    if query is None:
        query = ""
    query = query.strip()
    # add the search to history if needed
    if query is not None and query not in Dict[SEARCH_HISTORY_KEY]:
        Dict[SEARCH_HISTORY_KEY][query] = GetThumbnail(query)
        Dict.Save()
    # add tags from settings/etc
    query = ProcessQuery(query)
    # check if query has sorting already, if so go to the date menu
    tags = query.split()
    for tag in tags:
        if tag.startswith('sort:'):
            return DateMenu(query=query)
    # go to the sorting menu
    return SortMenu(query=query)


@route(PREFIX + '/sortmenu/{query}')
def SortMenu(query):
    oc = ObjectContainer(title2=L('sorting'), no_history=True)
    oc.add(DirectoryObject(key=Callback(DateMenu, query=query), title=unicode(L('no_sort'))))
    for item in SORT_TAGS:
        oc.add(DirectoryObject(key=Callback(DateMenu, query="{} {}".format(query, item)),
                               title=u"{} {}".format(L('sort_by'), L(item))))
    return oc


@route(PREFIX + '/datemenu/{query}')
def DateMenu(query):
    if query is None:
        query = ""
    oc = ObjectContainer(title2=L('post_age'), no_history=True)
    oc.add(GetPhotoAlbum(title=L('date_all'), query=query, page=0, time=0))
    for days in DATE_VIEWS:
        oc.add(GetPhotoAlbum(query=query, time=Dict[TIME_KEY] - days*DAY_IN_SECONDS,
                             title="{} {}".format(days, L('date_day') if days <= 1 else \
                                                        L('date_days'))))
    return oc

      
@route(PREFIX + '/getphotoalbum', page=int, time=int)
def GetPhotoAlbum(title, query, page=0, time=0):
    return DirectoryObject(key=Callback(Pages, query=query.strip(), time=time), title=title)


@route(PREFIX + '/pages', offset=int, time=int, total_pages=int)
def Pages(query, time=0, total_pages=None, offset=0):
    """List Page 1 to 20 + next button, then 21 to 40, etc"""
    Log("GELBOORU: {}, {}, {}".format(time, total_pages, offset))
    oc = ObjectContainer()
    limit = int(Prefs['limit'])
    if total_pages is None:
        # make an api call to find out the total number of pages this query will produce
        # limit=0 still returns the total count
        posts = XML.ElementFromURL(SEARCH_URL.format(server=Prefs['server'], tags=query, limit=0, page=0, time=time),
                                   headers={'Cookie': Dict['cookie-%s'%Prefs['server']]}, cacheTime=0).xpath("//posts")[0]
        total_pages = max(1, int(posts.get('count')) / limit)
    if total_pages == 1: # if its just 1 page, go right to the images
            return Page(tags=query, limit=limit, page=0, time=time)
    for i in range(offset, offset+min(total_pages, PAGE_LIMIT)):
        phash = page_hash(query, limit, i, time)
        oc.add(PhotoAlbumObject(key=Callback(Page, tags=query, limit=limit, page=i, time=time),
                                rating_key=str(phash),
                                title="{} {}".format(L('Page'), i+1),
                                thumb=Dict[PAGE_THUMBS].get(phash, R(ICON))))
    if offset + PAGE_LIMIT < total_pages:
        oc.add(NextPageObject(key=Callback(Pages, query=query, time=time, total_pages=total_pages,
                                           offset=offset+min(PAGE_LIMIT, total_pages)),
                              title=L('more')))
    return oc


def page_hash(tags, limit, page, time):
    return hash("{}{}{}{}".format(tags,limit,page,time))


@route(PREFIX + '/page', limit=int, page=int, time=int)
def Page(tags, limit, page=0, time=0):
    oc = ObjectContainer()
    phash = page_hash(tags,limit,page,time)
    posts = JSON.ObjectFromURL(SEARCH_URL.format(server=Prefs['server'], tags=tags, limit=limit,
                                                 page=page, time=time)+"&json=1",
                               headers={'Cookie': Dict['cookie-%s'%Prefs['server']]}, cacheTime=0)
    for post in posts:
        # get image paths from the xml
        file_url = post.get('file_url', "%s/images/%s/%s" % (Prefs['server'], post['directory'], post['image']))
        sample_url = "%s/samples/%s/sample_%s.jpg" % (Prefs['server'], post['directory'], post['hash']) if post['sample'] else file_url
        thumbnail_url = "%s/thumbnails/%s/thumbnail_%s.jpg" % (Prefs['server'], post['directory'], post['hash'])
        pid, tags, score, date = post['id'], post['tags'], post['score'], post['change']
        image = file_url if bool(Prefs['imagesize']) else sample_url
        if phash not in Dict[PAGE_THUMBS]:
            Dict[PAGE_THUMBS][phash] = thumbnail_url
            Dict.Save()
        if image.endswith('webm'):
            continue
        oc.add(PhotoObject(url=image, title="{} (s:{})".format(pid, score), summary=tags,
                           thumb=Resource.ContentsOfURLWithFallback(thumbnail_url,
                                                                    fallback=R(ICON))))
    return oc
