from os import walk
import csv
import glob
import dominate
from dominate.tags import *

data = []

def main():
    data = getData()
    for item in data:
        renderDetail(item)
        print("rendering %s.html done" % item[0])
    renderIndex(data)
    print("rendering index.html done")

# get csv data
def getData():
    data = []
    f = glob.glob('./data/*.csv')
    for file in f:
        with open(file) as csvfile:
            reader = csv.reader(csvfile)
            i=0
            subdata = []
            for row in reader:
                subdata.append(row)
        key = file[7:-4]
        data.append((key, subdata))
    return data


# render index
def renderIndex(data):
    page = dominate.document(title='dni\'s comic collection index page!')
    with page.add(div(id='content')):
        total = countTotal(data)
        h2('Total: %s' % total)
        for row in data:
            key = row[0]
            subdata = row[1]
            title = subdata[0][0]
            h3(a(title, href='%s.html' % key))
            count = countEntries(subdata)
            p("Gesamt: %s" % count)

    file = open("dist/index.html","w")
    file.write(page.render())
    file.close()

def renderDetail(data):
    key = data[0]
    subdata = data[1]
    title = subdata[0][0]
    page = dominate.document(title='dni\'s comics - %s' % title)
    with page.head:
        link(rel='stylesheet', href='detail.css')
    with page.add(div(id='content')):
        h1(title)
        with table().add(tbody()):
            i = True
            for row in subdata:
                l = tr()
                for col in row:
                    if(i == True):
                        col = ""
                        i = False
                    l.add(td(col))
    file = open("dist/%s.html" % key,"w")
    file.write(page.render())
    file.close()


def countTotal(data):
    total = 0
    for subdata in data:
        total += countEntries(subdata)
    return total


def countEntries(subdata):
    count = 0
    for row in subdata:
        first = True
        for col in row:
            if(first):
                first = False
            else:
                if(col):
                    count+=1
    return count





main()
