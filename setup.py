from setuptools import setup

setup(
    name='pth_utils',
    version='0.1',
    py_modules=['pth_utils'],
    install_requires=[
        'Click', 'requests', 'lxml', 'requests_oauthlib', 'cssselect'
    ],
    entry_points='''
        [console_scripts]
        pth_utils=pth_utils:cli
    ''',
)