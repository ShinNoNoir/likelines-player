LikeLines-Player
============

*Welcome to the new home for the LikeLines player component. The original prototype is still available on the [Knight-Mozilla repository](https://github.com/Knight-Mozilla/likelines-mojo).*

## Introduction
Conventional online video players do not make the inner structure of the video apparent, making it hard to jump straight to the interesting parts. LikeLines provides users with a navigable heat map of interesting regions for the videos they are watching. The novelty of LikeLines lies in its combination of content analysis and both explicit and implicit user interactions.

The LikeLines system is being developed in the [Delft Multimedia Information Retrieval Lab](http://dmirlab.tudelft.nl/) at the Delft University of Technology.


## ACM Multimedia 2012 Demo
Running the demo requires:

 * A HTML5-compatible browser supporting the Canvas element and JavaScript.
 * Internet access (for the YouTube API and jQuery library).
 * Python 2.6+ (for the backend reference implementation) with the following packages:
   * Flask
   * PyMongo
   * Flask-PyMongo
 * MongoDB (for the backend).

You can download the code via `git` or through the Github web interface. Once downloaded and unpacked to a directory, three processes need to be started in order to run the demo. These three processes can best be run in separate terminals or screens.

The first process is starting a web server (or use an existing one) which will serve demo web page and the LikeLines JavaScript library. Note that you cannot simply open the web page locally (the browser would simply refuse to execute JavaScript in a local context):

```sh
$ cd likelines-player
$ python -m SimpleHTTPServer 8080
```

Next step is to make sure a MongoDB server is running on the default port. You can start the MongoDB server by simply executing `mongod`:

```sh
$ mongod
```

The final step is to run the backend server for LikeLines. This server will receive requests to store and aggregate user playback behaviour:

```sh
$ cd likelines-player/server
$ python -m LikeLines.server -p 9090
```

When the three processes are running, please point your browser to [http://localhost:8080/examples/acmmm2012_demo.html](http://localhost:8080/examples/acmmm2012_demo.html) to start the demo.

## Roadmap and plans
 * A new minor release is planned around November 12th, 2012, which will contain a more polished demo interface and should have a simpler way of running the demo.