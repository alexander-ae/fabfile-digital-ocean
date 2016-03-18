# -*- coding: utf-8 -*-

from StringIO import StringIO

from fabric.api import run, env, cd, sudo, put
from fabric.colors import red, yellow
from fabric.contrib.files import append, upload_template
from fabric.operations import get
from fabric.decorators import task
import requests
from requests.auth import HTTPBasicAuth

from .secrets import load_secrets

secrets = load_secrets()

env.hosts = secrets["hosts"]

APT_GET_PACKAGES = [
    'build-essential',
    'python-dev',
    'libjpeg62',
    'libjpeg-dev',
    'libfreetype6',
    'libfreetype6-dev',
    'libtiff4-dev',
    'libwebp-dev',
    'liblcms1-dev',
    'libxslt-dev',
    'mercurial',
    'libssl-dev',
    'libncurses5-dev'
]


def notice(s):
    """ Muestra un mensaje colorido en consola """
    print(red('### ') + yellow(s, bold=True))


@task
def update():
    """ Actualiza el servidor """
    run('sudo apt-get update && sudo apt-get upgrade -y')


@task
def install_packages():
    """ Instala la lista de paquetes """
    run("apt-get install -y " + " ".join(APT_GET_PACKAGES))


@task
def new_user(admin_username, admin_password):
    """ Crea un nuevo usuario y le otorga permisos de administración """

    # Create the admin group and add it to the sudoers file
    admin_group = 'admin'
    run('addgroup {group}'.format(group=admin_group))
    run('echo "%{group} ALL=(ALL) ALL" >> /etc/sudoers'.format(
        group=admin_group))

    # Create the new admin user (default group=username); add to admin group
    run('adduser {username} --disabled-password --gecos ""'.format(
        username=admin_username))
    run('adduser {username} {group}'.format(
        username=admin_username,
        group=admin_group))

    # Set the password for the new admin user
    run('echo "{username}:{password}" | chpasswd'.format(
        username=admin_username,
        password=admin_password))


@task
def add_swap(memory='1G'):
    """ Crea, activa y optimiza la memoria swap """
    if memory == '0':
        return

    run('fallocate -l {} /swapfile'.format(memory))
    run('chmod 600 /swapfile')
    run('mkswap /swapfile')
    run('swapon /swapfile')

    append('/etc/fstab', '/swapfile   none    swap    sw    0   0')
    run('sysctl vm.swappiness=10')
    run('sysctl vm.vfs_cache_pressure=50')

    append('/etc/sysctl.conf', 'vm.swappiness = 10')
    append('/etc/sysctl.conf', 'vm.vfs_cache_pressure = 50')


@task
def config_python():
    """ Configura e instala los paquetes:
        pip, virtualenv, virtualenvwrapper, uwsgi, supervisor """
    env.user = 'devstaff'
    run('mkdir -p ~/{src,tmp,webapps}')

    with cd('src'):
        run('wget https://bootstrap.pypa.io/get-pip.py')
        sudo('rm -f /usr/lib/python2.7/dist-packages/six*')  # fix para remover six
        sudo('python get-pip.py')
        sudo('pip install virtualenv virtualenvwrapper uwsgi')


@task
def config_bashrc():
    """ Configurando el archivo .bashrc """
    notice("Configurando el archivo .bashrc")
    env.user = 'devstaff'
    append('~/.bashrc', 'alias python=python2;')
    append('~/.bashrc', 'export EDITOR=nano;')
    append('~/.bashrc', 'export TEMP=$HOME/tmp;')
    append('~/.bashrc', 'export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python2;')
    append('~/.bashrc', 'export WORKON_HOME=$HOME/.envs;')
    append('~/.bashrc', 'source /usr/local/bin/virtualenvwrapper.sh;')
    run('source ~/.bashrc')


@task
def config_postgresql(db_name, db_user, db_pw):
    """ Instala y configura postgresql """
    env.user = 'root'
    sudo('apt-get install -y libpq-dev postgresql postgresql-contrib')

    run('sudo -u postgres psql -c "create user {} with password \'{}\'"'.format(
        db_user, db_pw), pty=True)
    run('sudo -u postgres createdb --owner={} {}'.format(
        db_user, db_name), pty=True)


@task
def config_nginx():
    """ Instala y configura nginx """
    env.user = 'root'
    sudo('add-apt-repository -y ppa:nginx/stable')
    sudo('apt-get update')
    sudo('apt-get install -y nginx')
    upload_template('scripts/nginx.conf', '/etc/nginx/nginx.conf', context={},
        use_jinja=True, use_sudo=True)


@task
def config_supervisor():
    """ Instala y configura supervisord """
    notice('Instala y configura supervisord')
    env.user = 'root'
    sudo('pip install supervisor')
    put('scripts/supervisord.conf', '/etc/supervisord.conf')
    sudo('mkdir /etc/ini/')
    put('scripts/django_app.ini', '/etc/ini/{}.ini'.format(secrets["APP_NAME"]))


@task
def restart_supervisor():
    """ Reinicia supervisord """
    notice('Reinicia supervisord')
    sudo('supervisorctl reread')
    sudo('supervisorctl reload')
    # sudo('supervisorctl restart {}'.format('APP_NAME'))


@task
def config_bitbucket():
    """ Configuración de bitbucket """
    notice("Configuración de bitbucket")
    env.user = 'devstaff'

    # añadimos bitbucket a la lista de hosts conocidos
    run('touch ~/.ssh/known_hosts')
    run('ssh-keyscan -H bitbucket.org >> ~/.ssh/known_hosts')

    # leemos la clave ssh pública
    fd = StringIO()
    get('~/.ssh/id_rsa.pub', fd)
    id_rsa_pub = fd.getvalue()

    # enviamos la clave a bicbucket
    url = "https://api.bitbucket.org/1.0/repositories/{repo_user}/{repo_slug}/deploy-keys".format(
        repo_slug=secrets['REPO_SLUG'], repo_user=secrets['REPO_USER'])

    requests.post(url, auth=HTTPBasicAuth(secrets['BITBUCKET_USER'], secrets['BITBUCKET_PASSWORD']),
        data={'label': secrets['hosts'][0], 'key': id_rsa_pub})


@task
def config_repo():
    """ Clonamos y configuramos el repositorio """
    notice("Clonamos y configuramos el repositorio")
    env.user = 'devstaff'
    with cd('~/webapps'):
        run('hg clone {} {}'.format(secrets['REPO_URL'], secrets['REPO_SLUG']))


@task
def config_ssh():
    """ Creamos una nueva clave ssh """
    notice("Creamos una nueva clave ssh")
    env.user = 'devstaff'
    run('ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa -q')


@task
def config_server():
    """ Configura el servidor por primera vez """
    env.user = 'root'
    update()
    new_user(secrets['username'], secrets['username_pw'])
    install_packages()
    add_swap(secrets['swap_memory'])

    env.user = 'devstaff'
    config_python()
    config_bashrc()

    env.user = 'root'
    config_postgresql(secrets['db_name'], secrets['db_user'], secrets['db_pw'])
    config_nginx()

    config_supervisor()
    config_ssh()
    # config_bitbucket()
    # config_repo()
    notice('Todo correcto !')
