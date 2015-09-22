#!/usr/bin/env python3

import ast
import os
import re
import shlex
import subprocess

class Repository:
    def __init__(self, owner, repo,
                 source_branch='staging', dest_branch='master',
                 source_file_patterns = None,
                 astyle_file = 'astyle.spec',
                 astyle_ignore = None,
                 command = "make && make test"):
        self.owner = owner
        self.repo = repo
        self.source_branch = source_branch
        self.dest_branch = dest_branch
        self.source_file_patterns = (['*.cc','*.hh'] if source_file_patterns is None
                                     else source_file_patterns)
        self.astyle_file = astyle_file
        self.astyle_ignore = [] if astyle_ignore is None else astyle_ignore
        self.command = command


class PreserveCWD:
    def __enter__(self):
        self.cwd = os.getcwd()

    def __exit__(self, exc_type, value, traceback):
        os.chdir(self.cwd)

config_filename = os.path.join(os.path.dirname(__file__),
                               'bitbucket_config.txt')
if os.path.exists(config_filename):
    print('Loading from file')
    bitbucket_config = open(config_filename).read()
    parsed = ast.literal_eval(bitbucket_config)
    repositories_watching = [
        Repository(**kwargs) for kwargs in parsed
    ]
else:
    repositories_watching = []

def cleanup_string(string):
    # strip all ANSI color codes
    string = re.sub(r'\x1b[^m]*m','',string)

    # strip out lines hidden by \r
    return string

def callback(server,msg):
    if 'commits-noreply@bitbucket.org' not in msg['From']:
        return

    lines = [line.strip() for line in msg['Body'].split('\n')]

    fields = {}
    for line in lines:
        if ':' in line:
            colon_index = line.index(':')
            key = line[:colon_index].strip()
            value = line[colon_index+1:].strip()
            fields[key] = value

    url = fields['Repository URL']
    owner = url.split('/')[-3]
    repo = url.split('/')[-2]

    branch = fields['Branch']

    if fields['Summary'] == 'Corrected code formatting':
        return True

    for watching in repositories_watching:
        if (branch == watching.source_branch and
            owner == watching.owner and
            repo == watching.repo):
            with PreserveCWD() as preserve:
                return merge_into(server,watching)

    # Not a branch that we are watching, can ignore the email.
    return True


def merge_into(server, repo):
    print('Merging {} into {} on {}/{}'.format(
        repo.source_branch, repo.dest_branch, repo.owner, repo.repo))

    if not os.path.isdir(repo.repo):
        if os.path.lexists(repo.repo):
            print('{} file/symlink already exists, exiting'.format(repo.repo))
            return

        remote = 'git@bitbucket.org:{}/{}'.format(repo.owner, repo.repo)
        err = subprocess.call(['git','clone',remote])
        if err:
            print('Could not clone {}, exiting'.format(remote))
            return

    os.chdir(repo.repo)
    print('PWD = ',os.getcwd())

    err = subprocess.call(['git', 'checkout', repo.dest_branch])
    if err:
        print('Repository does not have {} branch, exiting'.format(repo.dest_branch))
        return
    subprocess.call(['git', 'pull'])

    err = subprocess.call(['git', 'checkout', repo.source_branch])
    if err:
        print('Repository does not have {} branch, exiting'.format(repo.source_branch))
        return
    subprocess.call(['git', 'pull'])

    is_ancestor = not subprocess.call(['git','merge-base','--is-ancestor',
                                       repo.source_branch, repo.dest_branch])
    if is_ancestor:
        print('No changes on {}'.format(repo.source_branch))
        return True

    subprocess.call(['git','checkout',repo.source_branch])
    author_email = subprocess.check_output(['git','show','--quiet','--format=%aE']).decode('utf-8')
    commit_message = subprocess.check_output(['git','show','--quiet','--format=%B']).decode('utf-8')

    if repo.astyle_file:
        if os.path.isfile(repo.astyle_file):
            with open(repo.astyle_file) as f:
                arguments = shlex.split(f.read())
            src_files = subprocess.check_output(['git','ls-files'] + repo.source_file_patterns)
            subprocess.call('astyle', '-n', arguments)

            matches_style = not subprocess.call(['git','diff','--exit-code'])
            if not matches_style:
                subprocess.call(['git','commit','-am','Corrected code formatting'])
                subprocess.call(['git','push','-u','origin',repo.source_branch])
                server.send(author_email,"You didn't format your code",
                            "You forgot to format your code before committing.  Tsk, tsk.")

        else:
            print('Astyle file {} not found, skipping'.format(repo.astyle_file))

    build_proc = subprocess.Popen(repo.command, shell=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, stderr = build_proc.communicate()
    err = build_proc.returncode
    if err:
        server.send(author_email, "Error while building/testing code",
                    cleanup_string(stdout))
    else:
        subprocess.call(['git','checkout',repo.dest_branch])
        subprocess.call(['git','merge',repo.source_branch,'--no-ff','-m',
                         commit_message])
        subprocess.call(['git','push'])
        server.send(author_email, "Push successful",
                    "Successfully merged {} into {}".format(repo.source_branch, repo.dest_branch))
        return True
