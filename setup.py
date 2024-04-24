import setuptools


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="RANsim",
    version="0.0.1",
    author="Erwin Yuanhao Li",
    author_email="erwinli@qq.com",
    description="RAN simulator with network slicing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ErwinLiYH/RANsim",
    project_urls={
        "Bug Tracker": "https://github.com/ErwinLiYH/RANsim/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=setuptools.find_packages(),
    python_requires=">=3.8",
)
