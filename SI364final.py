# Import statements
import os
from flask import Flask, render_template, session, redirect, url_for, flash, request
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FileField, PasswordField, BooleanField, SelectMultipleField, FloatField, TextAreaField, ValidationError
from wtforms.validators import Required, Length, Email, Regexp, EqualTo
from flask_script import Manager, Shell
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand
import requests
import json
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from flask_login import LoginManager, login_required, logout_user, login_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# App Setup
app = Flask(__name__)
app.debug = True
app.use_reloader = True
app.config['SECRET_KEY'] = 'hardtoguessstring'
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('DATABASE_URL') or "postgresql://localhost/wminckfinal"
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Manager setup
manager = Manager(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)

# Login Manager Setup
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'login'
login_manager.init_app(app)


# Spotify Manager Setup
client_credentials_manager = SpotifyClientCredentials(client_id='',client_secret='') # Need to input Client Id and Client Secret. Both are in comments on Canvas submission
spotify = spotipy.Spotify(client_credentials_manager=client_credentials_manager)


##############################
########### Models ###########
##############################

class User(UserMixin, db.Model):
    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, index=True)
    email = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    playlists = db.relationship("Playlist", backref="Users", lazy="dynamic")

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


user_playlist = db.Table('user_playlists',db.Column('song_id',db.Integer,db.ForeignKey('Songs.id')),db.Column('playlist_id',db.Integer,db.ForeignKey('Playlists.id')))


class Artist(db.Model):
    __tablename__ = "Artists"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    followers = db.Column(db.Integer)
    popularity = db.Column(db.Integer)
    songs = db.relationship("Song", backref="Song") # Establish a one-to-many relationship from Artists to Songs


class Song(db.Model):
    __tablename__ = "Songs"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String)
    artist = db.Column(db.String)
    artist_id = db.Column(db.Integer,db.ForeignKey("Artists.id"))
    album = db.Column(db.String)
    popularity = db.Column(db.Integer)
    url = db.Column(db.String)


class Genre(db.Model):
    __tablename__ = "Genres"
    id = db.Column(db.Integer, primary_key=True)
    genre = db.Column(db.String)


class Playlist(db.Model):
    __tablename__ = "Playlists"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String)
    user = db.Column(db.Integer, db.ForeignKey('Users.id'))
    songs = db.relationship('Song',secondary=user_playlist,backref=db.backref('Playlists',lazy='dynamic'),lazy='dynamic')


#############################
########### Forms ###########
#############################

class RegistrationForm(FlaskForm):
    email = StringField('Email:', validators=[Required(),Length(1,64),Email()])
    username = StringField('Username:',validators=[Required(),Length(1,64),Regexp('^[A-Za-z][A-Za-z0-9_.]*$',0,'Usernames must have only letters, numbers, dots or underscores')])
    password = PasswordField('Password:',validators=[Required(),EqualTo('password2',message="Passwords must match")])
    password2 = PasswordField("Confirm Password:",validators=[Required()])
    submit = SubmitField('Register User')

    def validate_email(self,field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_username(self,field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[Required(), Length(1,64), Email()])
    password = PasswordField('Password', validators=[Required()])
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Log In')


class ArtistEntryForm(FlaskForm):
    artist = StringField('Which artist would you like add?', validators=[Required()])
    submit = SubmitField('Submit')

    def validate_artist(self, field):
        if Artist.query.filter_by(name=field.data).first():
            raise ValidationError('Artist already exists in the database')


class SongEntryForm(FlaskForm):
    song = StringField('Which song would you like to add?', validators=[Required()])
    submit = SubmitField('Submit')

    def validate_song(self, field):
        if Song.query.filter_by(title=field.data).first():
            raise ValidationError('Song already exists in the database')


class GenreEntryForm(FlaskForm):
    genre = StringField('Which genre would you like to add?', validators=[Required()])
    submit = SubmitField('Submit')

    def validate_genre(self, field):
        if Genre.query.filter_by(genre=field.data).first():
            raise ValidationError('Genre already exists in the database')


class PlaylistCreationForm(FlaskForm):
    playlist = StringField('Playlist Name', validators=[Required()])
    song_picks = SelectMultipleField('Songs to include:',coerce=int)
    submit = SubmitField('Submit')


class PlaylistByGenreForm(FlaskForm):
    playlist = StringField('Playlist Name', validators=[Required()])
    genre = StringField('Which genre would you like a playlist for?', validators=[Required()])
    length = StringField("How many songs do you want on the playlist?", validators=[Required()])
    submit = SubmitField('Submit')


class UpdateButtonForm(FlaskForm):
    submit = SubmitField("Update")


class UpdatePlaylistForm(FlaskForm):
    new_song = StringField("Which song would you like to add to the playlist?", validators=[Required()])
    submit = SubmitField("Add Song")


class DeleteButtonForm(FlaskForm):
    submit = SubmitField("Delete")


class FavoritesForm(FlaskForm):
    favorite_artist = StringField("What is your favorite artist?", validators=[Required()])
    favorite_song = StringField("What is your favorite song?", validators=[Required()])
    submit = SubmitField("Submit")

########################################
########### Helper Functions ###########
########################################

def get_artist_info(artist):
    try:
        response = spotify.search(q=artist, type='artist', limit=1)
        return response
    except:
        return False


def get_song_info(song):
    try:
        response = spotify.search(q=song, type='track', limit=1)
        return response
    except:
        return False


def get_or_create_artist(artist):
    a = Artist.query.filter_by(name=artist).first()
    if a:
        return a
    else:
        data = get_artist_info(artist)
        name = data['artists']['items'][0]['name']
        followers = data['artists']['items'][0]['followers']['total']
        popularity = data['artists']['items'][0]['popularity']

        a = Artist(name=name, followers=followers, popularity=popularity)
        db.session.add(a)
        db.session.commit()
        return a


def get_or_create_song(song):
    s = Song.query.filter_by(title=song).first()
    if s:
        return s
    else:
        data = get_song_info(song)
        title = data['tracks']['items'][0]['name']
        artist = data['tracks']['items'][0]['album']['artists'][0]['name']
        album = data['tracks']['items'][0]['album']['name']
        popularity = data['tracks']['items'][0]['popularity']
        url = data['tracks']['items'][0]['external_urls']['spotify']

        a = get_or_create_artist(artist)

        s = Song(title=title, artist=artist, artist_id=a.id, album=album, popularity=popularity, url=url)
        db.session.add(s)
        db.session.commit()
        return s


def get_or_create_genre(genre):
    g = Genre.query.filter_by(genre=genre).first()
    if g:
        return g
    else:
        g = Genre(genre=genre)
        db.session.add(g)
        db.session.commit()
        return g


def get_or_create_playlist_by_genre(genre, current_user, length):
    genre = [genre.lower()]
    try:
        response = spotify.recommendations(seed_artists=None, seed_genres=genre, seed_tracks=None, limit=length, country=None)
        return response
    except:
        return False


def get_song_by_id(id):
    s = Song.query.filter_by(id=id).first()
    return s


def get_or_create_playlist(name, current_user, song_list=[]):
    p = current_user.playlists.filter_by(title=name).first()
    if p:
        return p
    else:
        p = Playlist(title=name)
        current_user.playlists.append(p)
        for song in song_list:
            p.songs.append(song)
        db.session.add(current_user)
        db.session.add(p)
        db.session.commit()
        return p


##############################
########### Routes ###########
##############################
@app.route('/register',methods=["GET","POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,username=form.username.data,password=form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('You can now log in!')
        return redirect(url_for('login'))
    return render_template('register.html',form=form)


@app.route('/login',methods=["GET","POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('index'))
        flash('Invalid username or password.')
    return render_template('login.html',form=form)


@app.route('/', methods=['GET', 'POST'])
def index():
    form = ArtistEntryForm()
    if form.validate_on_submit():
        get_or_create_artist(form.artist.data)
        flash("Artist was successfully added to the database")
        return redirect(url_for('see_artists'))
    return render_template('base.html',form=form)


@app.route('/add_song', methods=['GET', 'POST'])
def new_song():
    form = SongEntryForm()
    if form.validate_on_submit():
        get_or_create_song(form.song.data)
        flash("Song was successfully added to the database")
        return redirect(url_for('see_songs'))
    return render_template('song_entry.html',form=form)


@app.route('/add_genre', methods=['GET','POST'])
def new_genre():
    form = GenreEntryForm()
    if form.validate_on_submit():
        get_or_create_genre(form.genre.data)
        flash("Genre was successfully added to the database")
        return redirect(url_for('see_genres'))
    return render_template('genre_entry.html',form=form)


@app.route('/create_playlist',methods=["GET","POST"])
@login_required
def create_playlist():
    form = PlaylistCreationForm()
    songs = Song.query.all()
    choices = [(s.id, s.title) for s in songs]
    form.song_picks.choices = choices
    if form.validate_on_submit():
        song_picks = form.song_picks.data
        song_list = [get_song_by_id(id) for id in song_picks]
        get_or_create_playlist(name=form.playlist.data, current_user=current_user, song_list=song_list)
        return redirect(url_for('playlists'))
    return render_template('create_playlist.html', form=form)


@app.route('/create_playlist_by_genre',methods=["GET","POST"])
@login_required
def create_playlist_by_genre():
    form = PlaylistByGenreForm()
    if form.validate_on_submit():
        recommendations = get_or_create_playlist_by_genre(form.genre.data, current_user, int(form.length.data))
        song_picks = [get_or_create_song(song['name']) for song in recommendations['tracks']]
        get_or_create_playlist(name=form.playlist.data, current_user=current_user, song_list=song_picks)
        return redirect(url_for('playlists'))
    else:
        return render_template('create_playlist_by_genre.html', form=form)


@app.route('/playlists', methods=["GET","POST"])
@login_required
def playlists():
    form = DeleteButtonForm()
    user_playlists = current_user.playlists
    return render_template('playlists.html', playlists=user_playlists, form=form)


@app.route('/playlist/<playlist_id>', methods=["GET","POST"])
@login_required
def playlist(playlist_id):
    form = UpdateButtonForm()
    id = int(playlist_id)
    playlist = Playlist.query.filter_by(id=id).first()
    songs = playlist.songs.all()
    return render_template('playlist.html', playlist=playlist, songs=songs, form=form)


@app.route('/update/<playlist_id>', methods=["GET","POST"])
def update(playlist_id):
    form = UpdatePlaylistForm()
    id = int(playlist_id)
    playlist = Playlist.query.filter_by(id=id).first()
    if form.validate_on_submit():
        new_song = get_or_create_song(form.new_song.data)
        playlist.songs.append(new_song)
        db.session.add(playlist)
        db.session.commit()
        flash("Updated the {}  playlist".format(playlist.title))
        return redirect(url_for('playlists'))
    return render_template('update_playlist.html', playlist=playlist, form=form)


@app.route('/delete/<playlist_id>', methods=["GET","POST"])
def delete(playlist_id):
    id = int(playlist_id)
    playlist = Playlist.query.filter_by(id=id).first()
    db.session.delete(playlist)
    db.session.commit()
    flash("Deleted the {} playlist".format(playlist.title))
    return redirect(url_for('playlists'))


@app.route('/favorites_form')
def favorites():
    form = FavoritesForm()
    return render_template('favorites_form.html', form=form)


@app.route('/favorites', methods=['GET'])
def favorite_stuff():
    favorite_artist = request.args.get("favorite_artist")
    favorite_song = request.args.get("favorite_song")
    return render_template('favorites.html', favorite_artist=favorite_artist, favorite_song=favorite_song)


@app.route('/see_all_artists', methods=['GET', 'POST'])
def see_artists():
    artists = Artist.query.all()
    return render_template('all_artists.html', artists=artists)


@app.route('/see_all_songs', methods=['GET', 'POST'])
def see_songs():
    songs = Song.query.all()
    return render_template('all_songs.html', songs=songs)


@app.route('/see_all_genres', methods=['GET', 'POST'])
def see_genres():
    genres = Genre.query.all()
    return render_template('all_genres.html', genres=genres)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('index'))


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404



if __name__ == '__main__':
    db.create_all()
    manager.run()
