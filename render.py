import os
import csv
import dominate
from dominate.tags import *

alldata = {}


def main():
    getData("./data")
    for dir in alldata:
        createDistDir(dir)
        renderIndex(dir, alldata[dir])
        for subdata in alldata[dir]:
            if not (isinstance(subdata, basestring)):
                renderDetail(dir, subdata)

# data
def getData(dir):
    for dirname, dirnames, filenames in os.walk('./data'):
        alldata[dirname] = []
        for subdirname in dirnames:
            alldata[dirname].append(subdirname)
        for filename in filenames:
            alldata[dirname].append(getCsvData(os.path.join(dirname, filename)))

def getCsvData(file):
    with open(file) as csvfile:
        reader = csv.reader(csvfile)
        i=0
        subdata = []
        for row in reader:
            subdata.append(row)
    key = file[7:-4]
    return (key, subdata)

# create
def createPage(page, key):
    filename = os.path.join("./dist/", "%s.html" % key)
    content = page.render()
    file = open(filename,"w", encoding='utf8')
    file.write(content)
    file.close()
    print("rendering %s done" % filename)

def createDistDir(dir):
    dir = dir.replace("data", "dist")
    if not os.path.exists(dir):
        os.makedirs(dir)
        print("created dir: %s" % dir)

# render
def renderIndex(dir, data):
    page = dominate.document(title='dni\'s comic collection index page! %s' % dir)
    with page.add(div(id='content')):
        if (dir == "./data"):
            total = countTotal()
            h2('Total: %s' % total)
        for row in data:
            if (isinstance(row, basestring)):
                # its a dir
                title = "%s/" % row
                href = '%s/index.html' % row
            else:
                split = row[0].split("/")
                href = '%s.html' % split.pop()
                title = row[1][0][0]

            h3(a(title, href=href))
            count = countEntries(row[1])
            if (count > 0):
                p("Gesamt: %s" % count)

    if(dir == "./data"):
        key = "index"
    else:
        key = "%s/index" % dir[7:]
    createPage(page, key)

def renderDetail(dir, data):
    key = data[0]
    subdata = data[1]
    title = subdata[0][0]
    page = dominate.document(title='dni\'s comics - %s' % title)
    with page.head:
        link(rel='stylesheet', href='http://d261tqllhzwogc.cloudfront.net/comics/detail.css')
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
    createPage(page, key)



# statistics
def countTotal():
    total = 0
    for key in alldata:
        for data in alldata[key]:
            total += countEntries(data)
    return total

def countEntries(subdata):
    count = 0
    firstRow = True
    for row in subdata:
        if(firstRow):
            firstRow = False
        else:
            firstColumn = True
            for col in row:
                if(firstColumn):
                    firstColumn = False
                else:
                    if(col):
                        count+=1
    return count

# execute program
main()
