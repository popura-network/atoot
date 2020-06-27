from setuptools import setup

__version__ = "1.0.1"

test_deps = [
    'pytest'
]

with open("README.rst", "r") as fh:
    long_description = fh.read()

setup(name='atoot',
      version=__version__,
      description='Asynchronous Python library for the Mastodon API',
      long_description=long_description,
      packages=['atoot'],
      install_requires=[
          'aiohttp>=3.6.2', 
      ],
      tests_require=test_deps,
      url='https://github.com/popura-network/atoot',
      author='zhoreeq',
      author_email='zhoreeq@protonmail.com',
      license='MIT',
      keywords='mastodon api asyncio',
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Intended Audience :: Developers',
          'Topic :: Communications',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 3',
      ]
)
