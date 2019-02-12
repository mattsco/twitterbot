##Twitter Bot V2.1 by Mattsco.
#Fix numbers of followers
##Inspired from Simon Robain's code.

import time
import re
import pandas as pd, numpy as np
import dataiku
from datetime import date, datetime, timedelta
from birdy.twitter import UserClient, TwitterApiError
import random
import os.path
import json
import signal

MAX_USER_RETWEET = 100
MAX_QUERY = 10
TIMEOUT = 3


path_r = "/home/dataiku/matt/dss_bot/managed_datasets/reporting/"

def connection_to_twitter():
    print "connecting to twitter."
    conf = dataiku.get_custom_variables()
    return UserClient(conf["CONSUMER_KEY"].strip(),conf["CONSUMER_SECRET"].strip(),\
    				  conf["ACCESS_TOKEN"].strip(),conf["ACCESS_TOKEN_SECRET"].strip())

def APITimeout(signum, frame):
    print "Forever is over!"
    raise Exception("API timeout")

#init timeout.
signal.signal(signal.SIGALRM, APITimeout)


def callTwitterWithTimeout(f, timeout=TIMEOUT):
    signal.alarm(timeout)
    try:
        r = None
        r = f()
    except Exception, exc:
        print exc
    signal.alarm(0)
    return r


def followers_won(dataset):
    print "get followers/ids"
    path = "/".join(dataset.get_location_info()["info"]["path"].split("/")[:-1])+"/"
    path1 = path+"current_followers"
    path2 = path+"followers_won"

    CLIENT = connection_to_twitter()

    d = callTwitterWithTimeout(lambda: CLIENT.api["followers/ids"].get(stringify_ids= True, count=5000).data)

    if d==d:
    	my_followers = d.get("ids",[])
    	while d["next_cursor"]>0:
        	d = callTwitterWithTimeout(lambda: CLIENT.api["followers/ids"].get(stringify_ids= True, count=5000, cursor= d["next_cursor"]).data)
        	my_followers+= d.get("ids",[])

    #nbFollow = len(d["ids"])
    screen_name = dataiku.get_custom_variables()["screen_name"]

    d0 = callTwitterWithTimeout(lambda: CLIENT.api["users/show"].get(screen_name=screen_name, include_entities=False).data)
    nbFollow = d0["followers_count"]


    currentFollowersList = pd.DataFrame(my_followers, columns=["myFollower"])

    try:
        d1 = pd.read_csv(path1+"/followers.csv")
        previous_followers = set(d1.myFollower.values)
        now_followers = set(currentFollowersList.myFollower.astype(int).values)
        new_followers = list(now_followers - previous_followers)
        new_followers = ' '.join(str(f) for f in new_followers)
    except IOError:
        print "FIRST TIME?"
        new_followers = ""


    date = str(datetime.now()).split(":")[0]
    thedate = date.replace(" ","-")
    out = pd.DataFrame([[thedate, nbFollow, new_followers]], columns=["date","nb_followers","new_followers"])

    if len(new_followers)>1:
        out.to_csv(path2+"/won_at_"+thedate+".csv", index=0)

    newFollowersList = pd.DataFrame(new_followers.split(), columns=["myFollower"])
    currentFollowersList= pd.concat((currentFollowersList,newFollowersList)).drop_duplicates()
    currentFollowersList.to_csv(path1+"/followers.csv", index=0)

    out2 = pd.DataFrame([[screen_name, date+":00:00", d0["followers_count"], d0["friends_count"], d0["favourites_count"], d0["listed_count"]]], \
                columns=["screen_name","date","followers_count","friends_count","favourites_count","listed_count"])
    out2.to_csv(path_r+screen_name+"_"+thedate , index=0, header=False)
    
    return out

def get_tweet(hashtag, current_followers, liked_tweet,  follower_count_fold):
    print "Loading..."
    current_followers = current_followers.get_dataframe(columns=["myFollower"])

    if type(follower_count_fold)==type(False):
        if type(liked_tweet) == type(False):
            dont_bother = list(set(list(current_followers.values.flatten())))
        else:
            likes = liked_tweet.get_dataframe(columns=["user_id","query_time"])
            previousMonth = date.today() - timedelta(days=30)
            likes = likes[likes["query_time"]>str(previousMonth)]

            dont_bother = list(set(list(current_followers.values.flatten())+
                                   list(likes.user_id.values)))
    else:
        old_followers = follower_count_fold.get_dataframe(columns=["new_followers"])
        if type(liked_tweet) == type(False):
            dont_bother = list(set(list(current_followers.values.flatten())+
               list(old_followers.values.flatten())))
        else:
            likes = liked_tweet.get_dataframe(columns=["user_id","query_time"])
            previousMonth = date.today() - timedelta(days=30)
            likes = likes[likes["query_time"]>str(previousMonth)]

            dont_bother = list(set(list(current_followers.values.flatten())+
                   list(old_followers.values.flatten())+
                                   list(likes.user_id.values)))


    print "silent list size:", len(dont_bother)


    regex_RT = re.compile("RT @.*?:")

    ##Connexion to twitter api
    CLIENT = connection_to_twitter()

    full_fav = []
    fav_ids = []

    queries = hashtag.get_dataframe()
    All_queriesDedup = list(queries.hashtag.unique())

    if len(All_queriesDedup)>MAX_QUERY:
        queries = [ All_queriesDedup[i] for i in sorted(random.sample(xrange(len(All_queriesDedup)), MAX_QUERY)) ]
    else:
        queries = All_queriesDedup
    print
    print "Selecting", MAX_QUERY, "queries among", len(All_queriesDedup)
    print
    print "Selected queries:", queries
    print

    col_tweet = ["created_at","id","favorite_count","lang","retweet_count","text","in_reply_to_screen_name"]
    col_user = ["screen_name","verified","id","favourites_count","followers_count","friends_count","statuses_count",
                "listed_count","time_zone","utc_offset"]

    out = []

    for query in queries:
        print "looking for:", query
        data = callTwitterWithTimeout(lambda: CLIENT.api['search/tweets'].get(q=query, result_type= "mixed", count=200).data)
        if data is not None:
            statuses = dict(data)["statuses"]
            print "found ", len(statuses), "tweets!"
            print
            if len(statuses)>0:
                for tweet in statuses:
                    infos_tweet = pd.Series(tweet)[col_tweet]
                    infos_tweet.index = ["tweet_"+ i for i in infos_tweet.index]
                    d = infos_tweet.to_dict()

                    save_twittos(dict(pd.Series(tweet).user))

                    infos_tweet_users = pd.Series(dict(pd.Series(tweet).user))[col_user]
                    infos_tweet_users.index = ["user_"+ i for i in infos_tweet_users.index]
                    d.update(infos_tweet_users.to_dict())

                    d["query"] = query
                    d["query_time"] = str(datetime.utcnow())
                    try:
                        d["query_time_user"] = str(datetime.utcnow()+ timedelta(seconds=d["user_utc_offset"]))
                    except TypeError:
                        d["query_time_user"] = np.nan
                    if regex_RT.match(d["tweet_text"]):
                        d["tweet_retweeted"] = 1
                    else:
                        d["tweet_retweeted"] = 0

                    if int(d["user_id"]) not in dont_bother:
                        out.append(d)
        else:
            time.sleep(10)
    return pd.DataFrame(out).dropna(subset=["user_id"])

def get_retweets():
    number_of_tweet = 5

    # Recipe inputs
    retweet_tweets = dataiku.Dataset("retweet_tweets")
    retweet_tweets_df = retweet_tweets.get_dataframe().dropna(subset=["user_screen_name"])
    df_users = retweet_tweets_df.drop_duplicates(subset="user_screen_name").dropna(subset=["user_screen_name"]).set_index("user_screen_name")

    col_user = ["user_verified","user_id","user_favourites_count",
                "user_followers_count","user_friends_count","user_statuses_count",
                "user_listed_count","user_time_zone","user_utc_offset",
                "query","query_time","query_time_user"]

    col_tweet = ["created_at","id","favorite_count","lang","retweet_count","text","in_reply_to_screen_name"]
    out = []

    CLIENT = connection_to_twitter()
    for screen_name_retweet in retweet_tweets_df.user_screen_name.unique()[:MAX_USER_RETWEET]:
        full_fav = []
        fav_ids = []
        data =  callTwitterWithTimeout(lambda: CLIENT.api['statuses/user_timeline'].get(screen_name=screen_name_retweet,\
                                               count=100, include_rts=False, exclude_replies=True).data)
        if data is not None and len(data)>0:
            for tweet in data[:number_of_tweet]:
                infos_tweet = pd.Series(dict(tweet))[col_tweet]
                infos_tweet.index = ["tweet_"+ i for i in infos_tweet.index]
                d = infos_tweet.to_dict()
                d["user_screen_name"] = screen_name_retweet
                d["retweeted_tweet"] = df_users.ix[screen_name_retweet].tweet_text
                d.update(df_users.ix[screen_name_retweet][col_user].to_dict())
                out.append(d)
    return out

def save_twittos(d):
    name = d.get("id",0)
    path = dataiku.get_custom_variables()["dip.home"]+"/managed_folders/twittos/"
    if os.path.isfile(path+str(name)+".json"):
        with open(path+str(name)+".json", 'rb') as out:
            try:
                d0 = json.load(out)
            except ValueError:
                d0= {}
        d0.update(d)
    else:
        d0=d
    with open(path+str(name)+".json", 'wt') as out:
        res = json.dumps(d0, sort_keys=True, indent=4, separators=(',', ': '))
        out.write(res)

def score(df):
    """ Applying logistic regression coeff on followers/following features
        AUC = 0.73 """
    A = np.log(df["user_followers_count"])
    B = np.log(df["user_friends_count"])
    return 1-1.0/(1.0+np.exp(-0.837*A+1.016*B))

def simple_model():
    # Recipe inputs
    tweets_to_score = dataiku.Dataset("tweets_to_score")
    tweets_to_score_df = tweets_to_score.get_dataframe()

    tweets_to_score_df["score"] = tweets_to_score_df.apply(score, axis=1)

    tweets_to_score_df = tweets_to_score_df.sort_values(["score","tweet_retweet_count"], ascending=[0,0])
    tweets_to_score_df = tweets_to_score_df.drop_duplicates(subset= "user_screen_name")
    tweets_to_score_df = tweets_to_score_df.dropna(subset=["user_id"])
    tweets_to_score_df["user_id"] = tweets_to_score_df["user_id"].astype(int)
    return tweets_to_score_df

def like_tweets(dataset, dataframe=None, model_name=None):
    try:
        df = dataset.get_dataframe()
    except AttributeError:
        df = dataset
        dataset = dataframe
    df = df.sort_values(["score"], ascending=[0])
    df = df.dropna(subset=["tweet_id"]).drop_duplicates(subset=["tweet_id"])

    CLIENT = connection_to_twitter()
    conf = dataiku.get_custom_variables()
    ifav = []
    cpt = 0
    for i, tweet_id in enumerate(df.tweet_id.values):
        if cpt<int(conf['like_limit']):
            try:
                callTwitterWithTimeout(lambda: CLIENT.api['favorites/create'].post(id =int(tweet_id)))
                print cpt, "Liking tweet ",tweet_id
                ifav.append(int(tweet_id))
                time.sleep(3)
                cpt+=1
            except Exception,e:
                print "Something went wrong with tweet id {0} at index {1}".format(tweet_id, i)
                print str(e)
                pass


    path = "/".join(dataset.get_location_info()["info"]["path"].split("/")[:-1])+"/"
    path += "liked_tweet"


    thedate = str(datetime.now()).split(":")[0]
    thedate = thedate.replace(" ","-")

    if model_name is not None:
        df["model_name"] = model_name
    df[df["tweet_id"].isin(ifav)].to_csv(path+"/like_"+thedate+".csv", index=0, encoding='utf-8')
    out = df[df["tweet_id"].isin(ifav)]
    return out

def get_followers(dataset):
    CLIENT = connection_to_twitter()
    followers = []
    d = callTwitterWithTimeout(lambda: CLIENT.api["followers/list"].get(skip_status= False, count= 200, include_user_entities=True).data)
    followers += d["users"]
    cpt = 1
    while d["next_cursor"]>0:
        time.sleep(5)
        print "Got",len(followers),"followers."
        d = callTwitterWithTimeout(lambda: CLIENT.api["followers/list"].get(skip_status= False, count= 200,\
                                             include_user_entities=True, cursor=d["next_cursor"]).data)
        followers += d["users"]
        for u in d["users"]:
            save_twittos(dict(u))
        cpt+=1
        if cpt==15:
            print "waiting 15min..."
            time.sleep(900)
            cpt=1


    out = pd.DataFrame(followers)

    return out


def get_my_fav_list():
    CLIENT = connection_to_twitter()
    my_favs = []
    d =   callTwitterWithTimeout(lambda: CLIENT.api["favorites/list"].get(count=200).data)
    my_favs = [tweet["id"] for tweet in d]
    return my_favs


def delete_old_fav():
    CLIENT = connection_to_twitter()
    more_fav_to_delete = True
    while more_fav_to_delete:
        fav_to_delete = get_my_fav_list()
        print "I got {0} fav".format(len(fav_to_delete))
        if len(fav_to_delete) == 0:
            more_fav_to_delete = False
            print "no more fav."
        else:
            print "Deleting {0} fav".format(len(fav_to_delete))
            for tweet_id in fav_to_delete:
                time.sleep(0.05)
                try:
                    callTwitterWithTimeout(lambda: CLIENT.api['favorites/destroy'].post(id = tweet_id))
                    print "tweet", tweet_id, "deleted."
                except Exception,e:
                    print "Something went wrong with tweet id {0}".format(tweet_id)
                    print str(e)


def delete_like(dataset):
    df = dataset.get_dataframe(columns=["query_time","tweet_id"])
    previousDay = str(datetime.utcnow()-timedelta(days=1))
    previousDay2 = str(datetime.utcnow()-timedelta(days=3))
    df = df[df["query_time"]<=previousDay]
    df = df[df["query_time"]>previousDay2]
    cpt = 0
    if len(df)>0:
        CLIENT = connection_to_twitter()
        for tweet_id in df.tweet_id.values:
            try:
                callTwitterWithTimeout(lambda: CLIENT.api['favorites/destroy'].post(id = tweet_id))
                cpt+=1
		time.sleep(0.5)
                print "tweet",tweet_id,"deleted!"
            except TwitterApiError:
                print "Cant delete", tweet_id
        return cpt



