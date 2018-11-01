from setuptools import setup, find_packages
import sys, os

version = '0.3'

setup(name='penstock',
      version=version,
      description="",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Quintagroup, Ltd.',
      author_email='info@quintagroup.com',
      url='http://quintagroup.com/',
      license='Apache License 2.0',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          # -*- Extra requirements: -*-
            "gevent",
            "python-consul",
            "CouchDB",
            "PyYAML"
      ],
      entry_points={
          'console_scripts': [
              'penstock = penstock:main'
          ]
      },
      tests_require=[
            'mock',
            'nose',
            'munch'
      ]
      )
