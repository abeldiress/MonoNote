from flask import Flask, render_template, request, url_for, redirect, make_response, send_file, send_from_directory
from requests import HTTPError
import findpara as summarizer
import pyrebase
from datetime import datetime, timedelta
from validate_email import validate_email
import smtplib, ssl
import html
import json
import os
import base64
import stripe
import secret
from io import BytesIO

stripe.api_key = secret.secret_key

app = Flask(__name__)
name = 'MonoNote'

config = {
    'apiKey': "AIzaSyBJ15HXUFtIA3JbKTEwyg5mvWhjSFxT8Qg",
    'authDomain': "summary-note.firebaseapp.com",
    'databaseURL': "https://summary-note.firebaseio.com",
    'projectId': "summary-note",
    'storageBucket': "summary-note.appspot.com",
    'messagingSenderId': "115114333067",
    'appId': "1:115114333067:web:98602e493f1161d782d58e",
    'measurementId': "G-ZQRDHX15BM",
    'serviceAccount': "summary-note-firebase-adminsdk-c3yzh-c921d1c2a0.json"
}

public_config = {
    'apiKey': "AIzaSyDCjvUBMnCbavgXmuovzdYBzyJVMvxTfpQ",
    'authDomain': "public-notes-275120.firebaseapp.com",
    'databaseURL': "https://public-notes-275120.firebaseio.com",
    'projectId': "public-notes-275120",
    'storageBucket': "public-notes-275120.appspot.com",
    'messagingSenderId': "1245144544",
    'appId': "1:1245144544:web:4522c133123b72c9703785"
}

firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firebase.database()

public_firebase = pyrebase.initialize_app(public_config)
public_auth = public_firebase.auth()
public_db = public_firebase.database()

sender_email = 'realmononote@gmail.com'

@app.route('/sitemap')
def sitemap():
    return send_from_directory(directory='static', filename='sitemap.xml')

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        email = request.form['email']
        usr_name = request.form['name']
        country = request.form['country']
        msg = request.form['message']

        message = f'Name: {usr_name} \n\nEmail: {email} \n\nFrom: {country} \n\nMessage:\n{msg}'

        if validate_email(email):
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
                server.login(sender_email, 'nroalemefgahjisg')
                server.sendmail(sender_email, sender_email, message)
                server.quit()
            
            return render_template('msg-sent.html', name=name, invalidEmail=False)
        else:
            return render_template('msg-sent.html', name=name, invalidEmail=True)

    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')

        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
        user_info = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]
        
        return render_template('index.html', name=name, user_info=user_info)
    except:
        return render_template('index.html', name=name)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    global name
    if request.method == 'POST':
        user_name = request.form['name']
        email = request.form['email']
        pwd = request.form['pwd']
        confirm = request.form['confirm-pwd']

        if pwd != confirm:
            return render_template('signup.html', name=name, invalidPwd=True, content='Confirm password do not match. Try again.')

        try:
            user = auth.create_user_with_email_and_password(email, pwd)
        except:
            return render_template('signup.html', name=name, invalidPwd=True, content='This email is account already exists, try logging in.')

        accountInfo = auth.get_account_info(user['idToken'])
        initialData = {
            'name': user_name,
            'include_links': True,
            'include_images': True,
            'first_note': True,
            'stripeId': 'override',
            'plan': 'free',
            'points': 0
        }

        try:
            db.child('/users/' + accountInfo['users'][0]['localId'] + '/').push(initialData, user['idToken'])
        except ConnectionError:
            return 'No internet, good luck!'
        
        session_id = auth.create_custom_token(accountInfo['users'][0]['localId'])

        resp = make_response(redirect(url_for('verify')))
        resp.set_cookie('ssid', session_id)
        
        return resp

    return render_template('signup.html', name=name)

@app.route('/signup-mobile')
def signup_mobile():
    return render_template('signup-mobile.html', name=name)

@app.route('/verify')
def verify():
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')

        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))
    
    email = accountInfo['users'][0]['email']
    # checks if the email is not verified
    if not accountInfo['users'][0]['emailVerified']:
        auth.send_email_verification(user['idToken'])
        return render_template('verify.html', name=name, email=email)

    return redirect(url_for('notes'))

@app.route('/create')
def dash():
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))

    user_info = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]
    user_name = user_info['name']

    user_notes = db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').get(user['idToken']).val()
    if user_notes != None:
        limit = len(user_notes) >= 6
    else:
        limit = False

    return render_template('dashboard.html', name=name, user_name=user_name, user_info=user_info, limit=limit)

@app.route('/create/link', methods=['GET', 'POST'])
def link():
    if request.method == 'POST':
        session_id = request.cookies.get('ssid')
        
        link = request.form['link']     
        size = request.form['percentage']
        topic = request.form['topic']

        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])

        user_info = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]

        percentage = int()
        if size == '1':
            percentage = 15
        elif size == '2':
            percentage = 35
        elif size == '3':
            percentage = 55
        
        try:
            summary = summarizer.summarize(summarizer.extractText(link, _type='link'), percentage)
        except UnboundLocalError:
            return render_template('create-link.html', name=name, invalidLink=True)

        if user_info['include_images']:
            summary = summarizer.get_images(summary, topic)
        
        if user_info['include_links']:
            summary = summarizer.get_links(summary, topic)

        noteData = {
            'title': 'Summary Note - ' + topic,
            'date_created': str(datetime.now().date().year) + '-' + str(datetime.now().date().month) + '-' + str(datetime.now().date().day),
            'source': link,
            'content': summary
        }

        db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').push(noteData, user['idToken'])
        
        userInfoId = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val())[0]
        points = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]['points']

        db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child(userInfoId).update({
            'points': points + len(summary) * 100
        }, user['idToken'])

        return redirect(url_for('notes'))
    
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))
    
    return render_template('create-link.html', name=name)

@app.route('/create/text', methods=['GET', 'POST'])
def plain_text():
    if request.method == 'POST':
        session_id = request.cookies.get('ssid')

        text = request.form['text']     
        size = request.form['percentage']
        topic = request.form['topic']

        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])

        userInfoId = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val())[0]
        user_info = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]
        if user_info['plan'] == 'free':
            return redirect(url_for('notes'))

        percentage = int()
        if size == '1':
            percentage = 9
        elif size == '2':
            percentage = 35
        elif size == '3':
            percentage = 55
        
        summary = summarizer.summarize(summarizer.extractText(text, _type='text'), percentage)
        if user_info['include_images'] == True:
            summary = summarizer.get_images(summary, topic)
        
        if user_info['include_links'] == True:
            summary = summarizer.get_links(summary, topic)
        
        noteData = {
            'title': 'Summary Note - ' + topic,
            'date_created': str(datetime.now().date().year) + '-' + str(datetime.now().date().month) + '-' + str(datetime.now().date().day),
            'source': text,
            'content': summary
        }

        db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').push(noteData, user['idToken'])   
        points = user_info['points']

        db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child(userInfoId).update({
            'points': points + len(summary)
        }, user['idToken'])

        return redirect(url_for('notes'))

    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))
    
    userInfoId = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val())[0]
    user_info = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]

    if user_info['plan'] == 'free':
        return redirect(url_for('notes'))

    return render_template('create-text.html', name=name, user_info=user_info)

@app.route('/create/docx', methods=['GET', 'POST'])
def docx():
    if request.method == 'POST':
        session_id = request.cookies.get('ssid')

        f = request.files['file']
        size = request.form['percentage']
        topic = request.form['topic']

        if f:
            f.save(f.filename)
            
            user = auth.sign_in_with_custom_token(session_id)
            accountInfo = auth.get_account_info(user['idToken'])

            userInfoId = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val())[0]
            user_info = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]
            if user_info['plan'] == 'free':
                return redirect(url_for('notes'))

            percentage = int()
            if size == '1':
                percentage = 9
            elif size == '2':
                percentage = 35
            elif size == '3':
                percentage = 55
            
            summary = summarizer.summarize(summarizer.extractText(f.filename, _type='docx'), percentage)
            if user_info['include_images'] == True:
                summary = summarizer.get_images(summary, topic)
            
            if user_info['include_links'] == True:
                summary = summarizer.get_links(summary, topic)
            
            noteData = {
                'title': 'Summary Note - ' + topic,
                'date_created': str(datetime.now().date().year) + '-' + str(datetime.now().date().month) + '-' + str(datetime.now().date().day),
                'source': f.filename,
                'content': summary
            }

            os.remove(f.filename)

            db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').push(noteData, user['idToken'])
            
            userInfoId = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val())[0]
            points = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]['points']

            db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child(userInfoId).update({
                'points': points + len(summary)
            }, user['idToken'])

            return redirect(url_for('notes'))

        return 'no file'
    
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))

    return render_template('create-docx.html', name=name)

@app.route('/create/pdf', methods=['GET', 'POST'])
def pdf():
    if request.method == 'POST':
        session_id = request.cookies.get('ssid')

        f = request.files['file']
        size = request.form['percentage']
        topic = request.form['topic']

        if f:
            f.save(f.filename)
            
            user = auth.sign_in_with_custom_token(session_id)
            accountInfo = auth.get_account_info(user['idToken'])

            userInfoId = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val())[0]
            user_info = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]
            if user_info['plan'] == 'free':
                return redirect(url_for('notes'))
            
            percentage = int()
            if size == '1':
                percentage = 9
            elif size == '2':
                percentage = 35
            elif size == '3':
                percentage = 55
            
            summary = summarizer.summarize(summarizer.extractText(f.filename, _type='pdf'), percentage)
            if user_info['include_images'] == False:
                summary = summarizer.get_images(summary, topic)
            
            if user_info['include_links'] == True:
                summary = summarizer.get_links(summary, topic)
            
            noteData = {
                'title': 'Summary Note - ' + topic,
                'date_created': str(datetime.now().date().year) + '-' + str(datetime.now().date().month) + '-' + str(datetime.now().date().day),
                'source': f.filename,
                'content': summary
            }

            os.remove(f.filename)

            db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').push(noteData, user['idToken'])
            
            userInfoId = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val())[0]
            points = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]['points']

            db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child(userInfoId).update({
                'points': points + len(summary)
            }, user['idToken'])
        
            return redirect(url_for('notes'))

        return 'No File Available'
    
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))

    return render_template('create-pdf.html', name=name)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        pwd = request.form['pwd']
        try:
            user = auth.sign_in_with_email_and_password(email, pwd)
            accountInfo = auth.get_account_info(user['idToken'])
            userInfoId = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val())[0]

            session_id = auth.create_custom_token(accountInfo['users'][0]['localId'])

            # creates cookie of encrypted credentials
            resp = make_response(redirect(url_for('verify')))
            resp.set_cookie('ssid', session_id)
            return resp
        except HTTPError as e:
            e = str(e)
            if 'EMAIL_NOT_FOUND' in e:
                return render_template('login.html', invalidPwd=True, content='This account doesn\'t exist. Try a different email or create an account.', name=name)
            elif 'INVALID_PASSWORD' in e:
                return render_template('login.html', invalidPwd=True, content='Incorrect Password. Double check and try again.', name=name)
            elif 'TOO_MANY_ATTEMPTS_TRY_LATER' in e:
                return render_template('login.html', invalidPwd=True, content='Too many unsuccessful login attempts. Please try again later.', name=name)
                
        return redirect(url_for('verify'))
    
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')

        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
        return redirect(url_for('verify'))
    except Exception as e:
        print(e)
        return render_template('login.html', invalidPwd=False, name=name)

@app.route('/logout')
def logout():
    resp = make_response(redirect(url_for('index')))
    resp.set_cookie('ssid', '')
    return resp

@app.route('/notes')
def notes():
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))
        
    user_info = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]
    user_name = user_info['name']
    points = user_info['points']

    try:
        notes_unordered = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').get(user['idToken']).val().values())[0]['title']
        no_notes = False
    except AttributeError:
        no_notes = True
    
    if not no_notes:
        user_notes = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').get(user['idToken']).val().values())   
        note_ids = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').get(user['idToken']).val())

        for noteIndex in range(len(user_notes)):
            user_notes[noteIndex]['noteId'] = note_ids[noteIndex]

        return render_template('notes.html', name=name, user_notes=user_notes, length=len(user_notes), points=points, user_info=user_info)
    else:
        return render_template('notes.html', name=name, length=0, no_notes=no_notes, points=points, user_info=user_info)

@app.route('/note/<string:noteId>', methods=['GET', 'POST'])
def noteEdit(noteId):
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))

    note = dict(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').child(noteId).get(user['idToken']).val())
    note['content'] = [html.unescape(part) for part in note['content']]

    user_info = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]
    
    no_export = user_info['plan'] != 'free'
    if request.method == 'POST':
        new_content = list()
        for partIndex in range(len(note['content'])):
            try:
                new_content.append(request.form[str(partIndex) + '-edit'])
            except:
                pass
        
        noteData = {
            'title': note['title'],
            'date_created': note['date_created'],
            'source': note['source'],
            'content': new_content
        }

        db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').child(noteId).update(noteData, user['idToken'])
        note = dict(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').child(noteId).get(user['idToken']).val())

        return render_template('edit-note.html', save=True, note=note, name=name, length=len(note['content']), noteId=noteId, l=len(note['source']), no_export=no_export)
    
    return render_template('edit-note.html', save=False, note=note, name=name, length=len(note['content']), noteId=noteId, l=len(note['source']), no_export=no_export)

@app.route('/download/doc/<string:noteId>')
def downloadDoc(noteId):
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))

    note = dict(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').child(noteId).get(user['idToken']).val())

    return send_file(BytesIO(summarizer.download_as_doc(note['content'], note['title'], note['date_created'], noteId)), attachment_filename=note['title'] + '.docx', as_attachment=True, cache_timeout=0)

@app.route('/download/text/<string:noteId>')
def downloadText(noteId):
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))

    note = dict(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').child(noteId).get(user['idToken']).val())

    return send_file(BytesIO(summarizer.download_as_text(note['content'], note['title'], note['date_created'], noteId)), attachment_filename=note['title'] + '.txt', as_attachment=True, cache_timeout=0)

@app.route('/download/html/<string:noteId>')
def downloadHTML(noteId):
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))

    note = dict(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').child(noteId).get(user['idToken']).val())

    return send_file(BytesIO(summarizer.download_as_html(note['content'], note['title'], note['date_created'], noteId)), attachment_filename=note['title'] + '.html', as_attachment=True, cache_timeout=0)

@app.route('/download/pdf/<string:noteId>')
def downloadPDF(noteId):
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))

    note = dict(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').child(noteId).get(user['idToken']).val())

    return send_file(BytesIO(summarizer.download_as_pdf(note['content'], note['title'], note['date_created'], noteId)), attachment_filename=note['title'] + '.pdf', as_attachment=True, cache_timeout=0)

@app.route('/account', methods=['POST', 'GET'])
def account():
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))

    if request.method == 'POST':
        include_links = request.form.get('include-link')
        include_images = request.form.get('include-images')

        if include_images == 'on':
            include_images = True
        else:
            include_images = False

        if include_links == 'on':
            include_links = True
        else:
            include_links = False
        
        userInfoId = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val())[0]

        db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child(userInfoId).update({
            'include_images': include_images,
            'include_links': include_links
        }, user['idToken'])

    user_info = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]

    return render_template('account.html', name=name, accountInfo=accountInfo, user_info=user_info)

@app.route('/delete/note/<string:noteId>')
def deleteNote(noteId):
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))

    db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').child(noteId).remove(user['idToken'])
    return redirect(url_for('notes'))

@app.route('/subscribe', methods=['POST', 'GET'])
def subscribe():
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))

    userInfoId = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val())[0]
    user_info = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]

    if user_info['plan'] == 'paid':
        return redirect('billing')

    if request.method == 'POST':
        try:
            customer = stripe.Customer.create(
                email=accountInfo['users'][0]['email'],
                source=request.form['stripeToken']
            )
        except stripe.error.CardError:
            return 'The card number you entered was invalid. Try again <a href="/subscribe">here</a>.'
        
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{'plan': 'plan_H9qAIkFhKN7Wnz'}]
        )

        db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child(userInfoId).update({
            'stripeId': customer.id,
            'stripeSubscription': subscription.id,
            'plan': 'paid'
        }, user['idToken'])

        return redirect(url_for('billing'))

    return render_template('subscribe.html', name=name, publishable_key=secret.publishable_key)

@app.route('/billing')
def billing():
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))

    user_info = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]

    customer = None
    subscription = None

    if user_info['stripeId'] != 'override':
        customer = json.loads(str(stripe.Customer.retrieve(user_info['stripeId'])))
        subscription = json.loads(str(stripe.Subscription.retrieve(user_info['stripeSubscription'])))

    return render_template('billing.html', name=name, customer=customer, user_info=user_info)

@app.route('/public/note/<string:noteId>')
def publicNote(noteId):
    note = dict(public_db.child(noteId).get().val())
    return render_template('shared-note.html', note=note, name=name, length=len(note['content']), l=len(note['source']))

@app.route('/share/<string:noteId>')
def shareNote(noteId):
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))
    
    note = dict(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child('notes').child(noteId).get(user['idToken']).val())

    public_db.child(noteId).update(note)
    return render_template('edit-note.html', save=False, content='/public/note/' + noteId, note=note, name=name, length=len(note['content']), noteId=noteId, l=len(note['source']))

@app.route('/delete/account')
def deleteAccount():
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))
    
    user_info = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]
    
    if 'stripeId' in user_info and user_info['stripeId'] != 'override':
        stripe.Customer.delete(user_info['stripeId'])
    if 'stripeSubscription' in user_info:
        stripe.Subscription.delete(user_info['stripeSubscription'])

    db.child('/users/' + accountInfo['users'][0]['localId'] + '/').remove(user['idToken'])
    auth.delete_user_account(user['idToken'])
    return redirect(url_for('index'))


@app.route('/delete/billing')
def cancelSubscription():
    # if user hasn't logged in yet, it redirects to login page
    try:
        session_id = request.cookies.get('ssid')
        
        user = auth.sign_in_with_custom_token(session_id)
        accountInfo = auth.get_account_info(user['idToken'])
    except:
        return redirect(url_for('login'))
    
    user_info = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val().values())[0]
    userInfoId = list(db.child('/users/' + accountInfo['users'][0]['localId'] + '/').get(user['idToken']).val())[0]

    if 'stripeId' in user_info:
        stripe.Subscription.delete(user_info['stripeSubscription'])
        stripe.Customer.delete(user_info['stripeId'])
    
    db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child(userInfoId).child('stripeId').remove(user['idToken'])
    db.child('/users/' + accountInfo['users'][0]['localId'] + '/').child(userInfoId).child('stripeSubscription').remove(user['idToken'])

    return redirect(url_for('notes'))

@app.route('/newpwd/<string:email>')
def changePwd(email):
    try:
        auth.send_password_reset_email(email)
    except:
        pass
    return render_template('change-pwd.html', name=name, email=email)

@app.route('/forgotpwd', methods=['GET', 'POST'])
def fpwd():
    if request.method == 'POST':
        email = request.form['email']
        return redirect(url_for('changePwd', email=email))
    
    return render_template('forgot-pwd.html', name=name)

@app.route('/terms-of-serivce')
def tos():
    return render_template('tos.html')

@app.route('/privacy-policy')
def privacy():
    return render_template('privacy.html')

if __name__ == '__main__':
    app.run(debug=False)
