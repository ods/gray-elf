from setuptools import setup


setup(
    use_scm_version={
        "version_scheme": "no-guess-dev",
        "local_scheme": "dirty-tag",
    },
)
