# Kroftig backend kroftig/tests.py
#
# Copyright © 2017 Sean Bolton.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os
import subprocess
import tempfile
import traceback

from django.test import SimpleTestCase, TestCase
import graphene
from graphql.error import GraphQLError

from project.schema import Query
from .models import RepoModel


# ========== utility functions ==========

def format_graphql_errors(errors):
    """Return a string with the usual exception traceback, plus some extra fields that GraphQL
    provides.
    """
    if not errors:
        return None
    text = []
    for i, e in enumerate(errors):
        text.append('GraphQL schema execution error [{}]:\n'.format(i))
        if isinstance(e, GraphQLError):
            for attr in ('args', 'locations', 'nodes', 'positions', 'source'):
                if hasattr(e, attr):
                    if attr == 'source':
                        text.append('source: {}:{}\n'
                                    .format(e.source.name, e.source.body))
                    else:
                        text.append('{}: {}\n'.format(attr, repr(getattr(e, attr))))
        if isinstance(e, Exception):
            text.append(''.join(traceback.format_exception(type(e), e, e.stack)))
        else:
            text.append(repr(e) + '\n')
    return ''.join(text)


def set_up_test_repo():
    """Creates a repository for testing. Creates a temporary directory under, then untars the
    tar archive ./kroftig/fixtures/test_repo.tar.xz into that. Returns a tuple
    (tempfile temporary directory object, path to repo).
    """
    tempdir = tempfile.TemporaryDirectory(prefix='kroftig-tmp-')
    subprocess.run([
        'tar',
        '-C', tempdir.name,
        '-x', '-p',
        '-f', './kroftig/fixtures/test_repo.tar.xz',
    ])
    return tempdir


def tear_down_test_repo(tempdir):
    tempdir.cleanup()


def set_up_test_data(tempdir):
    path = os.path.join(tempdir.name, 'test_repo')
    RepoModel.objects.create(name='test_repo', path=path, description="Test Repo")


class TestContext(object):
    """An empty class for use as schema execution context."""
    pass


# ========== GraphQL schema general tests ==========

class RootTests(SimpleTestCase):
    def test_root_query(self):
        """Make sure the root query is 'Query'.

        This test is pretty redundant, given that every other query in this file will fail if this
        is not the case, but it's a nice simple example of testing query execution.
        """
        query = '''
          query RootQueryQuery {
            __schema {
              queryType {
                name  # returns the type of the root query
              }
            }
          }
        '''
        expected = {
            '__schema': {
                'queryType': {
                    'name': 'Query'
                }
            }
        }
        schema = graphene.Schema(query=Query)
        result = schema.execute(query)
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        self.assertEqual(result.data, expected, msg='\n'+repr(expected)+'\n'+repr(result.data))


# ========== Relay Node tests ==========

class RelayNodeTests(TestCase):
    """Test that model nodes can be retreived via the Relay Node interface."""

    # These tests are read-only, so we can set up the test repo once for all of them.
    @classmethod
    def setUpClass(cls):
        cls.tempdir = set_up_test_repo()

    @classmethod
    def tearDownClass(cls):
        tear_down_test_repo(cls.tempdir)

    def test_node_for_repo(self):
        set_up_test_data(self.tempdir)
        query = '''
          query {
            repo(name: "test_repo") {
              id
            }
          }
        '''
        schema = graphene.Schema(query=Query)
        result = schema.execute(query, context_value=TestContext())
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        repo_gid = result.data['repo']['id']
        query = '''
          query {
            node(id: "%s") {
              id
            }
          }
        ''' % repo_gid
        expected = {
          'node': {
            'id': repo_gid,
          }
        }
        result = schema.execute(query)
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        self.assertEqual(result.data, expected, msg='\n'+repr(expected)+'\n'+repr(result.data))

    def test_node_for_commit(self):
        set_up_test_data(self.tempdir)
        query = '''
          query TestNodeForCommit {
            repo(name: "test_repo") {
              commits(first: 1) {
                edges {
                  node {
                    id
                    message
                  }
                }
              }
            }
          }
        '''
        schema = graphene.Schema(query=Query)
        result = schema.execute(query, context_value=TestContext())
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        commit = result.data['repo']['commits']['edges'][0]['node']
        commit_gid = commit['id']
        commit_message = commit['message']
        query = '''
          query TestNodeForCommit2 {
            node(id: "%s") {
              id
              ...on Commit {
                message
              }
            }
          }
        ''' % commit_gid
        expected = {
          'node': {
            'id': commit_gid,
            'message': commit_message,
          }
        }
        result = schema.execute(query, context_value=TestContext())
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        self.assertEqual(result.data, expected, msg='\n'+repr(expected)+'\n'+repr(result.data))

    def test_node_for_branch(self):
        set_up_test_data(self.tempdir)
        query = '''
          query TestNodeForBranch {
            repo(name: "test_repo") {
              branches(first: 1) {
                edges {
                  node {
                    id
                    name
                  }
                }
              }
            }
          }
        '''
        schema = graphene.Schema(query=Query)
        result = schema.execute(query, context_value=TestContext())
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        branch = result.data['repo']['branches']['edges'][0]['node']
        branch_gid = branch['id']
        branch_name = branch['name']
        query = '''
          query {
            node(id: "%s") {
              id
              ...on Branch {
                name
              }
            }
          }
        ''' % branch_gid
        expected = {
          'node': {
            'id': branch_gid,
            'name': branch_name,
          }
        }
        result = schema.execute(query)
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        self.assertEqual(result.data, expected, msg='\n'+repr(expected)+'\n'+repr(result.data))

    def _test_node_for_tree_entry(self, path):
        set_up_test_data(self.tempdir)
        query = '''
          query TestNodeForTreeEntry {
            repo(name: "test_repo") {
              tree(rev: "master" %s first: 1) {
                edges {
                  node {
                    id
                    name
                    size
                  }
                }
              }
            }
          }
        ''' % path
        schema = graphene.Schema(query=Query)
        result = schema.execute(query, context_value=TestContext())
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        entry = result.data['repo']['tree']['edges'][0]['node']
        entry_gid = entry['id']
        entry_name = entry['name']
        entry_size = entry['size']
        query = '''
          query {
            node(id: "%s") {
              id
              ...on TreeEntry {
                name
                size
              }
            }
          }
        ''' % entry_gid
        expected = {
          'node': {
            'id': entry_gid,
            'name': entry_name,
            'size': entry_size,
          }
        }
        result = schema.execute(query, context_value=TestContext())
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        self.assertEqual(result.data, expected, msg='\n'+repr(expected)+'\n'+repr(result.data))

    def test_node_for_tree_entry(self):
        self._test_node_for_tree_entry('')

    def test_node_for_tree_entry_with_empty_path(self):
        self._test_node_for_tree_entry('path: ""')

    def test_node_for_tree_entry_with_path(self):
        self._test_node_for_tree_entry('path: "project"')


# ========== Repo tests ==========

class RepoTests(TestCase):
    # These tests are read-only, so we can set up the test repo once for all of them.
    @classmethod
    def setUpClass(cls):
        cls.tempdir = set_up_test_repo()

    @classmethod
    def tearDownClass(cls):
        tear_down_test_repo(cls.tempdir)

    def test_query_repos(self):
        """Query 'repos' field."""
        set_up_test_data(self.tempdir)
        query = '''
          query QueryReposQuery {
            repos {
              name
            }
          }
        '''
        expected = {
          'repos': [
            { 'name': 'test_repo' },
          ]
        }
        schema = graphene.Schema(query=Query)
        result = schema.execute(query)
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        self.assertEqual(result.data, expected, msg='\n'+repr(expected)+'\n'+repr(result.data))

    def test_query_repo(self):
        """Query 'repo' field."""
        set_up_test_data(self.tempdir)
        query = '''
          query QueryReposQuery {
            repo(name: "test_repo") {
              name
            }
          }
        '''
        expected = {
          'repo': {
            'name': 'test_repo',
          }
        }
        schema = graphene.Schema(query=Query)
        result = schema.execute(query, context_value=TestContext())
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        self.assertEqual(result.data, expected, msg='\n'+repr(expected)+'\n'+repr(result.data))

    def test_repo_current_branch(self):
        """Repo 'currentBranch' field."""
        set_up_test_data(self.tempdir)
        query = '''
          query QueryReposQuery {
            repo(name: "test_repo") {
              currentBranch
            }
          }
        '''
        expected = {
          'repo': {
            'currentBranch': 'master',
          }
        }
        schema = graphene.Schema(query=Query)
        result = schema.execute(query, context_value=TestContext())
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        self.assertEqual(result.data, expected, msg='\n'+repr(expected)+'\n'+repr(result.data))

    def test_repo_branches(self):
        """Repo 'branches' field."""
        set_up_test_data(self.tempdir)
        query = '''
          query RepoBranchesQuery {
            repo(name: "test_repo") {
              branches {
                edges {
                  node {
                    name
                    message
                    rev
                    ctime
                  }
                }
              }
            }
          }
        '''
        schema = graphene.Schema(query=Query)
        result = schema.execute(query, context_value=TestContext())
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        self.assertTrue('master' in map(lambda node: node['node']['name'],
                                        result.data['repo']['branches']['edges']),
                        msg=repr(result.data))

    def test_repo_commits(self):
        """Repo 'commits' field."""
        set_up_test_data(self.tempdir)
        query = '''
          query RepoCommitsQuery {
            repo(name: "test_repo") {
              commits {
                edges {
                  node {
                    message
                  }
                }
              }
            }
          }
        '''
        schema = graphene.Schema(query=Query)
        result = schema.execute(query, context_value=TestContext())
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        self.assertGreaterEqual(len(result.data['repo']['commits']['edges']), 4,
                                msg=repr(result.data)) # should have at least 4 commits

    def test_repo_commits_pagination(self):
        """Make sure that pagination works on CommitConnection."""
        set_up_test_data(self.tempdir)
        # retrieve the first three commits, plus a cursor for the next page
        query = '''
          query RepoCommitsPaginationTest {
            repo(name: "test_repo") {
              commits(first: 3) {
                edges {
                  node {
                    oid
                  }
                }
                pageInfo {
                  endCursor
                }
              }
            }
          }
        '''
        schema = graphene.Schema(query=Query)
        result = schema.execute(query, context_value=TestContext())
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        # save commit oids, and remove their nodes from edges
        oids = [oid for oid in map(lambda m: m['node']['oid'],
                                   result.data['repo']['commits']['edges'])]
        del result.data['repo']['commits']['edges'][:]
        # save cursor, and remove it from results (don't depend on cursor representation)
        cursor = result.data['repo']['commits']['pageInfo']['endCursor']
        result.data['repo']['commits']['pageInfo']['endCursor'] = 'REDACTED'
        expected = {
            'repo': {
                'commits': {
                    'edges': [
                        # redacted
                    ],
                    'pageInfo': {
                        'endCursor': 'REDACTED',
                    }
                }
            }
        }
        self.assertEqual(result.data, expected, msg='\n'+repr(expected)+'\n'+repr(result.data))
        # ask for the last result before endCurser, which should be the second result from above
        query = ('''
          query RepoCommitsPaginationTest2 {
            repo(name: "test_repo") {
              commits(last: 1, before: "''' +
          cursor +
              '''") {
                edges {
                  node {
                    oid
                  }
                }
              }
            }
          }
        ''')
        expected = {
            'repo': {
                'commits': {
                    'edges': [
                        { 'node': { 'oid': oids[1] } },
                    ],
                }
            }
        }
        result = schema.execute(query, context_value=TestContext())
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        self.assertEqual(result.data, expected, msg='\n'+repr(expected)+'\n'+repr(result.data))

    def test_repo_commits_with_rev(self):
        """Test the CommitConnection 'rev' field."""
        set_up_test_data(self.tempdir)
        # retrieve the first three commits
        query = '''
          query RepoCommitsWithRevTest {
            repo(name: "test_repo") {
              commits(first: 3) {
                edges {
                  node {
                    oid
                  }
                }
              }
            }
          }
        '''
        schema = graphene.Schema(query=Query)
        result = schema.execute(query, context_value=TestContext())
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        # save commit oids, and remove their nodes from edges
        oids = [oid for oid in map(lambda m: m['node']['oid'],
                                   result.data['repo']['commits']['edges'])]
        del result.data['repo']['commits']['edges'][:]
        expected = {
            'repo': {
                'commits': {
                    'edges': [
                        # deleted
                    ],
                }
            }
        }
        self.assertEqual(result.data, expected, msg='\n'+repr(expected)+'\n'+repr(result.data))
        # ask for commits from HEAD^, which should start at the second result from above
        query = '''
          query RepoCommitsWithRevTest2 {
            repo(name: "test_repo") {
              commits(rev: "HEAD^", first: 1) {
                edges {
                  node {
                    oid
                  }
                }
              }
            }
          }
        '''
        expected = {
            'repo': {
                'commits': {
                    'edges': [
                        { 'node': { 'oid': oids[1] } },
                    ],
                }
            }
        }
        result = schema.execute(query, context_value=TestContext())
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        self.assertEqual(result.data, expected, msg='\n'+repr(expected)+'\n'+repr(result.data))

    def _test_repo_tree(self, path, expected):
        """Test Repo 'tree' field."""
        set_up_test_data(self.tempdir)
        query = '''
          query RepoTreeTest {
            repo(name: "test_repo") {
              tree(rev: "master" %s first: 100) {
                edges {
                  node {
                    name
                    size
                  }
                }
              }
            }
          }
        ''' % path
        schema = graphene.Schema(query=Query)
        result = schema.execute(query, context_value=TestContext())
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        files = list(map(lambda node: node['node']['name'], result.data['repo']['tree']['edges']))
        files.sort()
        self.assertEqual(files, expected, msg='\n'+repr(expected)+'\n'+repr(result.data))
        size_present = any(map(lambda node: node['node']['size'] is not None,
                               result.data['repo']['tree']['edges']))
        self.assertTrue(size_present, 'none of the sizes in the query were non-null')

    # brittle, these depend on the contents of the repo:
    def test_repo_tree(self):
        expected = ['.gitignore', 'LICENSE', 'README.rst', 'kroftig', 'manage.py', 'project',
                    'requirements.txt']
        self._test_repo_tree('', expected)

    def test_repo_tree_with_empty_path(self):
        expected = ['.gitignore', 'LICENSE', 'README.rst', 'kroftig', 'manage.py', 'project',
                    'requirements.txt']
        self._test_repo_tree('path: ""', expected)

    def test_repo_tree_with_path(self):
        expected = ['__init__.py', 'schema.py', 'settings.py', 'urls.py', 'wsgi.py']
        self._test_repo_tree('path: "project"', expected)

    def test_repo_commit(self):
        """Test Repo 'commit' field."""
        set_up_test_data(self.tempdir)
        query = '''
          query RepoCommitTest {
            repo(name: "test_repo") {
              commit(rev: "HEAD") {
                oid
                message
                author
                authorTime
                authorEmail
                committer
                committerTime
                committerEmail
                parentIds
                tree {
                  edges {
                    node {
                      id
                    }
                  }
                }
              }
            }
          }
        '''
        schema = graphene.Schema(query=Query)
        result = schema.execute(query, context_value=TestContext())
        self.assertIsNone(result.errors, msg=format_graphql_errors(result.errors))
        commit = result.data['repo']['commit']
        for key in commit.keys():
            self.assertIsNotNone(commit[key], msg="Key '%s' should not be null" % key)
        length = len(commit['tree']['edges'])
        self.assertGreater(length, 1, msg=repr(result.data)) # should have more than 1 file
