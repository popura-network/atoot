from setuptools import setup

__version__ = "1.0"

test_deps = [
    'pytest'
]

setup(name='atoot',
      version=__version__,
      description='Asynchronous Python library for the Mastodon API',
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
