from setuptools import setup, find_packages

setup(
    name="youtube-analytics-cli",
    version="0.1.0",
    description="CLI tool for gathering YouTube Studio analytics",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "google-api-python-client>=2.108.0",
        "google-auth>=2.23.4",
        "google-auth-oauthlib>=1.1.0",
        "click>=8.1.7",
        "pandas>=2.1.4",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "youtube-analytics=youtube_analytics.cli:main",
        ],
    },
    python_requires=">=3.8",
)