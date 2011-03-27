# -*- coding: utf-8 -*-
import string
import random
import mimetypes
import cStringIO as StringIO

from bottle import request, response, get, post
from bottle import static_file, redirect, HTTPResponse
from bottle import mako_view as view
from PIL import Image
from pymongo import DESCENDING
import models as db

def _unique_filename(filename):
    """ Return a unique filename based on filename to save in the database."""
    result = filename.rsplit('.', 1)
    result[0] = '%s-%s' % (result[0],
                  ''.join(random.sample(string.letters + string.digits, 10)))
    result = '.'.join(result)
    if db.imagesfs.exists({'result':result}):
        return _unique_filename(filename)
    else:
        return result

@get(['/', '/list', '/list/:page#\d+#'])
@view('list.mako')
def list(page=0):
    ''' List messages. '''
    PAGE_SIZE = 5
    page = int(page)
    prev_page = None
    if page > 0:
        prev_page = page - 1
    next_page = None
    if db.messages.count() > (page + 1) * PAGE_SIZE:
        next_page = page + 1
    msgs = (db.messages.Message.find()
                .sort('date', DESCENDING)
                .limit(PAGE_SIZE).skip(page * PAGE_SIZE))
    return {'messages': msgs,
            'prev_page': prev_page,
            'next_page': next_page,
            }

@post('/create')
def create():
    ''' Save new message. '''
    if not (request.POST.get('nickname') and request.POST.get('text')):
        redirect('/')
    msg = db.messages.Message()
    msg.nickname = unicode(request.POST.get('nickname'))
    msg.text = unicode(request.POST.get('text'))
    msg.save()
    if 'image' in request.files:
        upload = request.files['image']
        filename = _unique_filename(upload.filename)
        # Only accept appropriate file extensions
        if not filename.lower().endswith(
                ('.jpg', '.jpeg', '.png', '.bmp', '.gif')):
            redirect('/')
        # Save fullsize image
        db.imagesfs.put(upload.file, filename=filename)
        # Save thumbnail
        image = Image.open(db.imagesfs.get_version(filename))
        image.thumbnail((80, 60), Image.ANTIALIAS)
        data = StringIO.StringIO()
        image.save(data, image.format)
        data.seek(0)
        db.thumbsfs.put(data, filename=filename)
        # Update image filename after images have successfully uploaded.
        msg.image = unicode(filename)
        msg.save()
    redirect('/')

@get('/:collection#(images|thumbs)#/:filename')
def get_image(collection, filename):
    ''' Send image or image thumb from file stored in the database. '''
    import urllib
    filename = urllib.unquote_plus(filename)
    fs = db.imagesfs if collection == 'images' else db.thumbsfs
    f = fs.get_version(filename)
    response.content_type = f.content_type or mimetypes.guess_type(filename)
    return HTTPResponse(f)

@get('/static/:filename#.+#')
def get_static_file(filename):
    ''' Send static files from ./static folder. '''
    return static_file(filename, root='./static')
