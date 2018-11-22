FROM python:3.6

ADD sf_ex_v2.py /
ADD config.py /
ADD requirements.txt /

RUN apt-get update && apt-get -qq install libgl1-mesa-glx
RUN pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

CMD [ "python", "./sf_ex_v2.py" ]
