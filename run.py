#!/usr/bin/python
import flask, flask.views
app = flask.Flask(__name__)

import time, os
from flask import jsonify
from threading import Thread
from hashlib import md5
from collections import OrderedDict
from random import randint as crypt
from utils import *


@app.route('/')
@app.route('/<page>')
def main(page="index"):    
    if page == 'logout':
        flask.session.pop('username', None)
        return flask.redirect('/')
    if os.path.isfile('templates/%s.html' % page):
        return flask.render_template(page+'.html')
    return flask.abort(404)


@app.route('/api')
@login
def rest_api():
    data = api()
    if not data:
        return flask.abort(404)
    data['servers'] = getServers()
    return jsonify(data), 200


@app.route('/download')
@app.route('/download/<version>')
@app.route('/download/<version>/<other>')
def download(version=None, other=None):
    source_uri = 'https://api.github.com/repos/LeChosenOne/LegendCraft/zipball/%s'
    download_uri = 'https://github.com/LeChosenOne/LegendCraft/releases/download/%s/%s' # tag, filename
    git_uri = 'https://github.com/LeChosenOne/LegendCraft/releases/%s'
    data = api()
    if not data:
        return flask.abort(404)
    data = data['releases']
    latest_tag = data[0]['tag_name']
    latest_file = data[0]['assets'][0]['name']
    src_aliases = ['src','source','fork','git']
    view_aliases = ['view', 'read', 'html', 'data', 'read']
    if not version: # Assume that they want to list all current downloads
        return flask.render_template('download.html', data=data)
    elif version.lower() == 'latest':
        if other:
            if other.lower() in src_aliases: 
                return flask.redirect(source_uri % data[0]['tag_name'])
            elif other.lower() == 'update':
                return str(latest_tag)
            else:
                return flask.abort(404)
        else:
            return flask.redirect(download_uri % (latest_tag, latest_file))
    else:
        try:
            tag, filename = None, None
            for release in data:
                if version == release['tag_name']:
                    tag, filename = release['tag_name'], release['assets'][0]['name']
                    break
            if not tag or not filename:
                return flask.abort(404)
        except:
            return flask.abort(404)
        if other:
            if other.lower() in src_aliases:
                return flask.redirect(source_uri % tag)
            elif other.lower() in view_aliases:
                return flask.redirect(git_uri % tag)
            else:
                return flask.abort(404)
        else:
            return flask.redirect(download_uri % (tag, filename))


@app.route('/license')
def license():
    return flask.redirect('https://raw.github.com/LeChosenOne/LegendCraft/master/License.txt')


@app.route('/software')
@login
def software():
    return 'Not done. xD'


@app.route('/wiki')
def wiki():
    return flask.redirect('http://minecraft.gamepedia.com/Custom_servers/legendcraft')


ran = False
def server_daemon():
    global ran
    if ran: return
    ran = True
    while True:
        time.sleep(120)
        # get the servers, check for inactive servers, remove old servers, and save servers
        #print '[DAEMON] Checking for inactive servers!'
        servers = getServers()
        if not servers:
            #print '[DAEMON] No servers to check for!'
            pass
        tmp = []
        for server in servers: # "server" being a index #
            difference = int(time.time()) - int(server['last_ping'])
            if difference > 480:
                print '[DAEMON] Removed stale server'
            else:
                tmp.append(server)
        saveServers(tmp)


@app.route('/heartbeat', methods=['GET'])
def server_heartbeat():
    # Collect the current POSIX time, so if the server is valid we get a good
    # start-process time to work with
    uptime = str(int(time.time()))
    required = ['name', 'players', 'max', 'version', 'url']
    args = flask.request.args

    # Lets see if we're missing the required GET variables...
    for requirement in required:
        if not requirement in args:
            return 'Bad request'

    # Make the dictionary of data to insert into the database of servers
    server = {}
    server['name'] = args['name']
    server['version'] = args['version']
    server['id'] = md5(server['name'] + server['version']).hexdigest()
    server['pcount'] = str(args['players'])
    server['pmax'] = str(args['max'])
    server['url'] = args['url']

    # Still not finished vars: "last_ping", and "uptime". Those are sorted now..
    # First we need to tell if the server is new or not. By looping through and finding ID's!
    # This is ugly, but we're not using a huge database for this so this is the best we get
    ids = getServerIds()
    servers = getServers()
    if server['id'] in ids:
        # It is already in the list... Lets update "last_ping"
        # This does the actual updating...
        editServer(server['id'], str(uptime), server['pcount'])
        return 'Updated'
    else:
        # It's a new server, so we're going to append it to the serverlist
        server['last_ping'], server['uptime'] = uptime, uptime
        servers.append(server)
        saveServers(servers)
        return 'Added'


@app.route('/servers')
def server_list():
    # First, we need to read the database...
    servers = getServers()

    # "servers" should be populated, or empty..
    if not servers:
        return flask.render_template('servers.html')

    # Assume "servers" is a list() of dict()'s with server data
    # So, lets return the data to the user, sorted by uptime!
    servers = sorted(servers, key=lambda k: k['uptime'])[::-1]

    # Take the time, convert their ugly POSIX time to humanly-readable-time
    for server in servers:
        # At a later time, we'll find the difference between the stored INITIAL heartbeat,
        # And the current time, giving us the seconds for the HR uptime
        difference = int(time.time()) - int(server['uptime'])
        server['uptime'] = date(relativedelta(seconds=difference))[0]

    return flask.render_template('servers.html', servers=servers)


class Login(flask.views.MethodView):
    def get(self):
        if 'username' in flask.session:
            return flask.redirect(flask.url_for('index'))
        if 'url' in flask.request.args:
            return flask.render_template('login.html', url=flask.request.args['url'])
        return flask.render_template('login.html')
    def post(self):
        if 'username' in flask.session:
            return flask.redirect('/')
        form = flask.request.form
        required = ['username', 'passwd']
        if not required[0] in form or not required[1] in form:
            error = 'You must have both a password and username!'
            return flask.render_template('login.html')
        if 'logout' in form:
            flask.session.pop('username', None)
            return flask.redirect(flask.url_for('login'))
        errors = {
            'blank': 'You must have both a username and password.',
            'incorrect': 'Incorrect username or password.',
            'notadmin': 'Authentication successful but user not admin.'
        }
        for r in required:
            if r not in form:
                return flask.render_template('login.html', error=errors['blank'])
            if form[r].strip() == '':
                return flask.render_template('login.html', error=errors['blank'])
        username = form[required[0]]
        passwd = form[required[1]]
        accountStatus = isauthed(username, passwd)
        if accountStatus == 1:
            flask.session[required[0]] = username
        elif accountStatus == 2:
            return flask.render_template('login.html', error=errors['notadmin'])
        else:
            return flask.render_template('login.html', error=errors['incorrect'])
        if 'url' in form:
            return flask.redirect(form['url'])
        return flask.redirect('/')


@app.errorhandler(404)
def page_not_found(error):
    return flask.render_template('404.html'), 404


# @app.after_request
# def add_header(response):
#     """
#         Add headers to both force latest IE rendering engine or Chrome Frame,
#         and also to cache the rendered page for 10 minutes.
#     """
#     response.headers['X-UA-Compatible'] = 'IE=Edge,chrome=1'
#     response.headers['Cache-Control'] = 'public, max-age=600'
#     return response


app.add_url_rule('/login', view_func=Login.as_view('login'), methods=['GET','POST'])


if __name__ == '__main__':
    # Create a thread to check for inactive servers...
    # This is the daemon that powers the /servers route
    thread = Thread(target = server_daemon, args = ())
    thread.start()

    # Debug should normally be false, so we don't display hazardous information!
    app.debug = True # Set it to true, to show awesome debugging information!
    app.secret_key = str(crypt(0, 1000000000000000)) # Randomize so sessions are reset on reboot
    app.run(host='0.0.0.0', port=4000)