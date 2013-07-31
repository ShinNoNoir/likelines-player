/*
 * LikeLines Player
 * Copyright (c) 2011-2013 R. Vliegendhart <ShinNoNoir@gmail.com>
 * 
 * Licensed under the MIT license:
 * 
 * Permission is hereby granted, free of charge, to any person obtaining 
 * a copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, including without limitation 
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, 
 * and/or sell copies of the Software, and to permit persons to whom the 
 * Software is furnished to do so, subject to the following conditions:
 * 
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 * 
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING 
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS 
 * IN THE SOFTWARE.
 */


/*--------------------------------------------------------------------*
 * REQUIREMENTS
 *--------------------------------------------------------------------*
 *
 *   1. jQuery must be loaded before the LikeLines library.
 *
 */

/* IE fix */
if (!window.console) window.console = {};
if (!window.console.log) window.console.log = function () { };

LikeLines = {};
(function(LikeLines){
	
	/*--------------------------------------------------------------------*
	 * Options
	 *--------------------------------------------------------------------*/
	LikeLines.options = {};
	LikeLines.options.defaults = {
		width:    425,  // NOTE: for now, these are the width/height 
		height:   356,  //       for the internal video player
		video:    undefined,
		backend:  undefined,
		onReady:  undefined,
		
		// Smoothing parameters and default kernel
		smoothingBandwidth: 1.0,
		kernelFunction: 'gaussian', /* name from LikeLines.Util.Kernels or kernel function */
		palette: 'heat',            /* name from LikeLines.Util.Palettes or palette function */
		
		// Explicit-Like/Implicit-Playback weight factors
		heatmapWeights: {
			likes:     1.0,
			playback:  1.0, // TODO: allow e.g. "max" value or numViewers as weight?
			seeks:     1.0,
			mca:       1.0
		},
		
		// Back-end Throttle
		backendThrottle: 5.0, // 1 request per 5 seconds
		
		// Back-end read-only flag
		backendReadOnly: false,
		
		// Not an option, but an auto-generated property:
		videoCanonical: undefined
	};
	
	
	/*--------------------------------------------------------------------*
	 * YouTube API
	 *--------------------------------------------------------------------*/
	LikeLines.YouTube = {};
	LikeLines.YouTube.isAPILoaded = false;
	LikeLines.YouTube.isLoadingAPI = false;
	LikeLines.YouTube._onLoadedCallbacks = [];
	LikeLines.YouTube.loadAPI = function(onLoaded) {
		if (LikeLines.YouTube.isLoadingAPI || LikeLines.YouTube.isAPILoaded) {
			if (onLoaded && LikeLines.YouTube.isAPILoaded) {
				onLoaded();
			}
			else {
				LikeLines.YouTube._onLoadedCallbacks.push(onLoaded);
			}
			return;
		}
		
		LikeLines.YouTube.isLoadingAPI = true;
		if (onLoaded)
			LikeLines.YouTube._onLoadedCallbacks.push(onLoaded);		
		
		// 1: Put the required callback in the global namespace: 
		onYouTubeIframeAPIReady = function() {
			LikeLines.YouTube.onYouTubePlayerAPIReady();
		};
		
		// 2: Load the YouTube API:
		var tag = document.createElement('script');
		tag.src = "//www.youtube.com/iframe_api";
		var firstScriptTag = document.getElementsByTagName('script')[0];
		firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);
		
	};
	LikeLines.YouTube.onYouTubePlayerAPIReady = function() {
		LikeLines.YouTube.isLoadingAPI = false;
		LikeLines.YouTube.isAPILoaded = true;
		for (var i=0; i < LikeLines.YouTube._onLoadedCallbacks.length; i++) {
			LikeLines.YouTube._onLoadedCallbacks[i]();
		}
		LikeLines.YouTube._onLoadedCallbacks = [];
	};
	
	
	/*
	 * Internal player for playing YouTube videos.
	 * 
	 * Events fired by YT API:
	 *    After creation:              onStateChange  UNSTARTED -1
	 *                                 onReady
	 *    After first loadVideo:       onStateChange  CUED 5
	 *    Subsequent loadVideo calls:  onStateChange  UNSTARTED -1
	 *                                 onStateChange  CUED 5
	 */
	LikeLines.YouTube.InternalPlayer = function (llplayer, video, onReady) {
		this.llplayer = llplayer;
		this.video = video;
		this.metadata = undefined;
		this.ready = false;
		
		this.ytstate = undefined;
		this._onVideoLoadedCallbacks = [];
		this._videoLoaded = false; // YT
		this._videoFullyLoaded = false; // YT+metadata
		
		this.ytplayer = undefined;
		var self = this;
		LikeLines.YouTube.loadAPI(function () {
			self.ytplayer = new YT.Player(self.llplayer.gui.videoNode, {
				height: self.llplayer.options['height'],
				width: self.llplayer.options['width'],
				videoId: self.video[self.type],
				events: {
					'onReady': function (evt) {
						self.llplayer.gui.onInternalPlayerChanged(self, player.internalPlayer.ytplayer.getIframe());
						self.ready = true;
						// workaround for https://code.google.com/p/gdata-issues/issues/detail?id=4706
						self.ytplayer.addEventListener('onStateChange', function (evt) { self.onPlayerStateChange(evt); });
						self.onPlayerStateChange( {'data': -1} );
						if (onReady)
							onReady();
					},
					'onError': function (evt) { console.log('onError', evt); } // TODO: onError is not used. Idea: use metadata.error?
				},
				playerVars: {
					version: 3, /* gives early access to getDuration(), but only for first initial video */
					rel: 0 /* temporary fix for issue 5 */
				}
			});
		});
		this._fetchMetadata(function() {self._checkVideoFullyLoaded();} );
	};
	LikeLines.YouTube.InternalPlayer.prototype.type = 'YouTube';
	LikeLines.YouTube.InternalPlayer.prototype.onPlayerStateChange = function (evt) {
		console.log('onPlayerStateChange', evt.data, {
			'-1': 'UNSTARTED',
			 0: 'ENDED',
			 1: 'PLAYING',
			 2: 'PAUSED',
			 3: 'BUFFERING',
			 5: 'CUED'
		}[evt.data], this.getCurrentTime(), new Date().getTime()/1000, evt);
		
		var prev_ytstate = this.ytstate;
		this.ytstate = evt.data;
		
		var firstLoad = prev_ytstate == undefined && evt.data == -1/*unstarted*/;
		var subSequentLoad = prev_ytstate !== undefined && evt.data == YT.PlayerState.CUED;
		if (firstLoad || subSequentLoad) {
			this._videoLoaded = true;
			this._checkVideoFullyLoaded();
		}
		
		var evtType = {
			 0: 'ENDED',
			 1: 'PLAYING',
			 2: 'PAUSED'
		}[evt.data];
		if (evtType !== undefined) {
			this.llplayer.onPlaybackEvent(evtType);
		}
	}
	LikeLines.YouTube.InternalPlayer.prototype.loadVideo = function (src, onReady) {
		this._onVideoLoadedCallbacks[src[this.type]] = onReady;
		
		this.video = src;
		this.metadata = undefined;
		this._videoLoaded = false;
		this._videoFullyLoaded = false;
		this.ytplayer.cueVideoById(src[this.type]); // do not autoplay
		
		var self = this;
		this._fetchMetadata(function() {self._checkVideoFullyLoaded();} );
	};
	LikeLines.YouTube.InternalPlayer.prototype._checkVideoFullyLoaded = function() {
		if (!this._videoFullyLoaded && this.metadata !== undefined && this._videoLoaded) {
			this._videoFullyLoaded = true;
			this.llplayer.onVideoLoaded();
			
			var callback = this._onVideoLoadedCallbacks[ this.video[this.type] ];
			delete this._onVideoLoadedCallbacks[ this.video[this.type] ];
			if (callback)
				callback();
		}
	};
	LikeLines.YouTube.InternalPlayer.prototype.pause = function() {
		this.ytplayer.pauseVideo();
	};
	LikeLines.YouTube.InternalPlayer.prototype.play = function() {
		this.ytplayer.playVideo();
	};
	LikeLines.YouTube.InternalPlayer.prototype.isPaused = function() {
		return this.ytplayer.getPlayerState() == YT.PlayerState.PAUSED;
	};
	LikeLines.YouTube.InternalPlayer.prototype.isPlaying = function() {
		return this.ytplayer.getPlayerState() == YT.PlayerState.PLAYING;
	};
	LikeLines.YouTube.InternalPlayer.prototype.getCurrentTime = function() {
		return this.ready ? this.ytplayer.getCurrentTime() : 0;
	};
	LikeLines.YouTube.InternalPlayer.prototype.getDuration = function() {
		// FIXME: Metadata can be *incorrect* (bug in YouTube API data)
		return (this.metadata && 'data' in this.metadata) ? this.metadata.data.duration : this.ytplayer.getDuration();
	};
	
	LikeLines.YouTube.InternalPlayer.prototype.seekTo = function (timepoint, allowSeekAhead) {
		this.ytplayer.seekTo(timepoint, allowSeekAhead);
	};
	
	LikeLines.YouTube.InternalPlayer.prototype._fetchMetadata = function(callback) {
		var metadata_url = '//gdata.youtube.com/feeds/api/videos/' +
		                   this.video[this.type] + '?v=2&alt=jsonc&prettyprint=true&callback=?';
		
		var self = this;
		jQuery.getJSON(metadata_url, function(json) {
			self.metadata = json;
			callback();
		});
	};
	
	// Always pre-load YouTube's API, might want to change this later on:
	LikeLines.YouTube.loadAPI();
	
	
	/*--------------------------------------------------------------------*
	 * Player
	 *--------------------------------------------------------------------*/
	LikeLines.Player = function (id_or_node, options) {
		this.node = ('string' == typeof id_or_node) ? document.getElementById(id_or_node) : id_or_node;
		this.id = this.node.id;
		
		this.options = LikeLines.Util.merge(options, LikeLines.options.defaults);
		this.internalPlayer = undefined;
		
		this.backend = undefined; // To be created after VideoLoaded event
		this.ticker = undefined;
		this.lastTickTC = 0;
		this.createGUI();
	};
	
	LikeLines.Player.prototype.createGUI = function () {
		var gui = new LikeLines.GUI.Default(this, this.node);
		var videoNode = gui.videoNode;
		
		this.gui = gui;
		this.loadVideo(this.options['video'], this.options['onReady']);
	};
	
	LikeLines.Player.prototype.onVideoLoaded = function () {
		// TODO: add support for user event handlers?
		console.log('onVideoLoaded');
		
		if (this.internalPlayer.type === 'HTML5') {
			this.options['videoCanonical'] = video_url;
		}
		else {
			this.options['videoCanonical'] = this.internalPlayer.type + 
			                           ':' + this.internalPlayer.video[this.internalPlayer.type];
		}
		
		if (this.backend !== undefined) {
			this.backend.sendInteractions([], true);
		}
		this.backend = new LikeLines.BackendServer(this.options['backend'], this.options['videoCanonical'], this.options);
		this.backend.createNewInteractionSession();
		this.updateHeatmap();
		
		var self = this;
		this.ticker = window.setInterval(function () {
			self.lastTickTC = self.getCurrentTime();
			self.onPlaybackEvent('TICK');
		}, 250);
	};
	
	LikeLines.Player.prototype.onPlaybackEvent = function (evtType) {
		var cur_ts = new Date().getTime() / 1000;
		var interaction = [cur_ts, evtType, this.getCurrentTime(), this.lastTickTC];
		
		var forceSend = evtType === 'ENDED' || evtType === 'LIKE';
		this.backend.sendInteractions([interaction], forceSend);
	};
	
	LikeLines.Player.prototype.loadVideo = function (video_url, onReady) {
		this.options['video'] = video_url;
		this.options['videoCanonical'] = undefined; // will be set after the video is loaded
		
		if (this.ticker !== undefined) {
			window.clearInterval(this.ticker);
			this.ticker = undefined;
			this.lastTickTC = 0;
		}
		
		var src = LikeLines.Util.determineVideoSource(video_url);
		
		// Delegate call to internalPlayer if it can handle the video player,
		// otherwise create a suitable internalPlayer.
		// 
		// Note: The onReady callback can thus be passed along different paths! 
		if (this.internalPlayer && this.internalPlayer.type in src) {
			this.internalPlayer.loadVideo(src, onReady);
		}
		else {
			if ('HTML5' in src) {
				console.error('HTML5 video support not yet implemented');
			}
			else if ('YouTube' in src) {
				this.internalPlayer = new LikeLines.YouTube.InternalPlayer(this, src, onReady);
			}
		}
	};
	
	LikeLines.Player.prototype.pause = function() {
		this.internalPlayer.pause();
	};
	LikeLines.Player.prototype.play = function() {
		this.internalPlayer.play();
	};
	LikeLines.Player.prototype.isPaused = function() {
		return this.internalPlayer.isPaused();
	};
	LikeLines.Player.prototype.isPlaying = function() {
		return this.internalPlayer.isPlaying();
	};
	LikeLines.Player.prototype.getDuration = function () {
		return this.internalPlayer ? this.internalPlayer.getDuration() : -1;
	};
	
	LikeLines.Player.prototype.getCurrentTime = function () {
		return this.internalPlayer ? this.internalPlayer.getCurrentTime() : 0;
	};
	LikeLines.Player.prototype.seekTo = function (timepoint, allowSeekAhead) {
		if (this.internalPlayer) {
			this.internalPlayer.seekTo(timepoint, allowSeekAhead || false);
		}
	};
	
	LikeLines.Player.prototype.onLike = function () {
		var now = this.getCurrentTime();
		this.gui.heatmap.addMarker(now);
		this.onPlaybackEvent('LIKE');
	};
	
	LikeLines.Player.prototype.updateHeatmap = function (limit, nolikes) {
		var self = this;
		
		var d = this.getDuration();
		var playback = LikeLines.Util.zeros(d);
		
		var video = this.options['videoCanonical'];
		this.backend.aggregate(function (aggregate) {
			// Ignore callback if different video has been loaded in the meantime
			// TODO: Possibly merge this into a future LikeLines.BackendServer implementation 
			if (video !== self.options['videoCanonical']) {
				return;
			}
			
			var playbacks = aggregate['playbacks'];
			var likedPoints = undefined;
			var myLikes = aggregate['myLikes'];
			
			if (limit === undefined) {
				limit = playbacks.length;
			}
			else {
				limit = Math.min(limit, playbacks.length);
			}
			
			for (var i=0; i < limit; i++) {
				var playbackSession = playbacks[i];
				for (var j=0; j < playbackSession.length; j++) {
					var playedSegment = playbackSession[j];
					var begin = Math.floor(playedSegment[0]);
					var end = Math.floor(playedSegment[1]);
					
					for (var s=begin; s <= end && s < d; s++) {
						playback[s]++;
					}
				}
			}
			
			if (!nolikes) {
				likedPoints = aggregate['likedPoints'];
			}
						
			var heatmap = self.gui.heatmap.computeHeatmap(d,
				likedPoints, /*likes*/
				playback, /* playback */
				undefined, /* seeks */
				undefined /* mca */
			);
			self.gui.heatmap.paintHeatmap(heatmap);
			
			self.gui.heatmap.clearMarkers();
			for (var i=0; i < myLikes.length; i++) {
				self.gui.heatmap.addMarker(myLikes[i]);
			}
		});
	};
	
	/*--------------------------------------------------------------------*
	 * GUI
	 *--------------------------------------------------------------------*/
	LikeLines.GUI = {};
	LikeLines.GUI.Default = function (llplayer, node) {
		var $ = jQuery;
		var self = this;
		
		this.llplayer = llplayer;
		
		this.node = node;
		this.videoNode = $(document.createElement('div')).addClass('LikeLines video')[0];
		this.controls = document.createElement('div');
		this.heatmap = new LikeLines.GUI.Navigation.Heatmap(this);
		this.likeButton = $('<button>Like</button>').addClass('LikeLines like')[0];
		
		$(node).addClass('LikeLines player')
		       .append(this.videoNode)
		       .append($(this.controls).addClass('LikeLines controls')
		                               .append(this.heatmap.node)
		                               .append(this.likeButton));
		
		$(this.likeButton).click(function(e) {
			self.llplayer.onLike();
		});
	};
	LikeLines.GUI.Default.prototype.onInternalPlayerChanged = function (internalPlayer, node) {
		$(node).addClass('LikeLines video');
	};
	LikeLines.GUI.Navigation = {};
	LikeLines.GUI.Navigation.Heatmap = function (gui) {
		var $ = jQuery;
		var self = this;
		
		this.gui = gui;
		
		this.node = document.createElement('div');
		this.heatmap = document.createElement('div');
		this.markersbar = document.createElement('div');
		
		this.canvas = document.createElement('canvas');
		this.canvasWidth = gui.llplayer.options.width;
		this.canvasHeight = 16;
		
		this.markers = []; // Contains timepoints (Number) for now
		
		$(this.node).addClass('LikeLines navigation')
		            .append(this.heatmap)
		            .append(this.markersbar);
		$(this.heatmap).addClass('LikeLines heatmap')
		               .append(this.canvas);
		$(this.canvas).width(this.canvasWidth)
		              .height('100%')
		              .prop({
		                  width: this.canvasWidth,
		                  height: this.canvasHeight
		              });
		$(this.markersbar).addClass('LikeLines markersbar');
		
		var mousedownHandler = function(e) {
			var domNode = this;
			var resumePlayingAfterSeek = !self.gui.llplayer.isPaused();
			// TODO: check whether this ^ gives desirable behaviour when HTML5 player is added.
			
			var dragHandler = function(e) {
				self.onDrag(e, domNode, true);
				domNode.blur();
				e.preventDefault();
				return false;
			};
			$(window).mousemove(dragHandler);
			var mouseupHandler = function(e) {
				$(this).unbind('mousemove', dragHandler);
				$(this).unbind('mouseup', mouseupHandler);
				
				domNode.blur();
				e.preventDefault();
				
				self.onDrag(e, domNode, false);
				if (resumePlayingAfterSeek) {
					self.gui.llplayer.play();
				}
				return false;
			};
			$(window).mouseup(mouseupHandler);
			
			domNode.blur();
			e.preventDefault();
			return false;
		};
		
		var $canvas = $(this.canvas);
		var $heatmap = $(this.heatmap);
		
		$canvas.mousedown(mousedownHandler);
		$heatmap.mousedown(mousedownHandler);
	};
	LikeLines.GUI.Navigation.Heatmap.prototype.addMarker = function(timepoint) {
		var $ = jQuery;
		var self = this;
		
		if ($.inArray(timepoint, this.markers) !== -1) {
			return;
		}
		else {
			this.markers.push(timepoint);
		}
		
		var markersbar = $(this.markersbar);
		var marker = $(document.createElement('div')).addClass('marker').appendTo(markersbar);
		
		var w = markersbar.outerWidth();
		var d = this.gui.llplayer.getDuration();
		var x = timepoint*w/d - marker.outerWidth()/2; 
		
		marker.css('left', x);
		marker.data('timepoint', timepoint);
		marker.click(function (e) {
			self.gui.llplayer.seekTo(timepoint, true);
		});
		
	};
	LikeLines.GUI.Navigation.Heatmap.prototype.clearMarkers = function() {
		var $ = jQuery;
		
		this.markers = [];
		$(this.markersbar).empty();
	};
	LikeLines.GUI.Navigation.Heatmap.prototype.paintHeatmap = function(heatmap) {
		var ctx = this.canvas.getContext('2d');
		var w = this.canvasWidth;
		var elWidth = 1;
		var elHeight = this.canvasHeight;
		
		var palette = this.gui.llplayer.options.palette;
		if (typeof palette === 'string') {
			palette = LikeLines.Util.Palettes[palette];
		}
		
		for(var i = 0; i < w; i++) {
			ctx.beginPath();
			
			var val = heatmap[i];
			var color = palette(val);
			ctx.fillStyle = 'rgb(' + color[0] + ',' + color[1] + ',' + color[2] + ')';
			
			ctx.fillRect(i, 0, elWidth, elHeight);
		}
	};
	LikeLines.GUI.Navigation.Heatmap.prototype.paintPalette = function(palette) {
		// for debugging purposes
		var heatmap = LikeLines.Util.scaleArray([0,1], this.canvasWidth);
		
		var oldPalette = this.gui.llplayer.options.palette;
		if (palette !== undefined) {
			this.gui.llplayer.options.palette = palette;
		}
		this.paintHeatmap(heatmap);
		this.gui.llplayer.options.palette = oldPalette;
	};
	LikeLines.GUI.Navigation.Heatmap.prototype.computeHeatmap = function(duration, likes, playback, seeks, mca) {
		/*
		 * duration: number of seconds of corresponding video
		 * likes: [timepoints] of likes
		 * playback: [weights] per time bin from playing behaviour
		 * seeks: [timepoints] of seeks
		 * mca: [weights] per time bin from content analysis
		 */
		var w = this.canvasWidth;
		var heatmap = LikeLines.Util.zeros(w);
		
		// get options
		var K = this.gui.llplayer.options.kernelFunction;
		var h = this.gui.llplayer.options.smoothingBandwidth;
		var heatmapWeights = this.gui.llplayer.options.heatmapWeights;
		
		// convert all timecode-level evidence to an Array(w)
		var timecodeEvidence = {
			likes:     ['kernelSmooth',  likes],
			playback:  ['scaleArray',    playback],
			seeks:     ['kernelSmooth',  seeks],
			mca:       ['scaleArray',    mca]
		};
		
		for (var prop in timecodeEvidence) {
			var op = timecodeEvidence[prop][0];
			var evidence = timecodeEvidence[prop][1];
			
			if (evidence === undefined) {
				delete timecodeEvidence[prop];
				continue;
			}
			
			var arr;
			if (op === 'kernelSmooth') {
				var arr = [];
				var f_smooth = LikeLines.Util.kernelSmooth(evidence, undefined, K);
				var step = (duration-1 - 0)/(w-1);
				
				for (var i = 0; i < w-1; i++) {
					var x = i*step;
					arr.push(f_smooth(x, h));
				}
				arr.push(f_smooth(duration-1, h));
			}
			else if (op === 'scaleArray') {
				arr = LikeLines.Util.scaleArray(evidence, w);
			}
			
			// For now, scale it to [-1,1]
			var max, min;
			max = min = arr[0];
			for (var i = 1; i < w; i++) {
				max = Math.max(max, arr[i]);
				min = Math.min(min, arr[i]);
			}
			var scale = Math.max(Math.abs(min), Math.abs(max));
			if (scale !== 0) {
				for (var i = 0; i < w; i++) {
					arr[i] /= scale;
				}
			}
			timecodeEvidence[prop] = arr;
		}
		
		
		var scale = null;
		for (var i=0; i < w; i++) {
			for (var prop in timecodeEvidence) {
				heatmap[i] += timecodeEvidence[prop][i] * heatmapWeights[prop];
			}
			heatmap[i] = Math.max(0, heatmap[i]);
			scale = Math.max(scale, heatmap[i]);
		}
		if (scale !== 0) {
			for (var i=0; i < w; i++) {
				heatmap[i] /= scale;
			}	
		}
		
		return heatmap;
	};
	LikeLines.GUI.Navigation.Heatmap.prototype.eventToTimepoint = function(e, domNode) {
		var player = this.gui.llplayer;
		var $node = $(domNode);
		
		// fix for issue 17
		var x = e.clientX + 
		        ((window.pageXOffset !== undefined) ? window.pageXOffset 
		                                            : (document.documentElement || document.body).scrollLeft) - 
		        $node.offset().left;
		var w = $node.outerWidth();
		var d = player.getDuration();
		
		if (x < 0) {
			x = 0;
		}
		else if (x >= w) {
			x = w-1;
		}
		return (d !== -1) ? x*d/w : -1;
	}
	LikeLines.GUI.Navigation.Heatmap.prototype.onDrag = function(e, domNode, ongoing) {
		var player = this.gui.llplayer;
		var timepoint = this.eventToTimepoint(e, domNode);
		if (timepoint != -1) {
			player.seekTo(timepoint, !ongoing);
			if (ongoing) {
				this.gui.llplayer.pause();
			}
		}
	};
	
	/*--------------------------------------------------------------------*
	 * Back-end Server (represents 1 interaction session)
	 *--------------------------------------------------------------------*/
	LikeLines.BackendServer = function (baseUrl, videoId, options) {
		if (baseUrl === undefined) {
			console.log('BackendServer(): Warning: no back-end specified');
		}
		else if (baseUrl.charAt(baseUrl.length-1) != '/') {
			baseUrl += '/';
		}
		this.baseUrl = baseUrl;
		this.videoId = videoId;
		this.buffer = [];
		this.lastSend = 0;
		this.sessionToken = undefined;
		this.readonly = options['backendReadOnly'];
		this.options = options || LikeLines.options.defaults;
	}
	LikeLines.BackendServer.prototype.createNewInteractionSession = function () {
		if (this.readonly) return;
		if (this.baseUrl === undefined) {
			console.log('BackendServer.createNewInteractionSession(): Warning: no back-end specified');
			return;
		}
		
		var self = this;
		var cur_ts = new Date().getTime() / 1000;
		
		var url = this.baseUrl + 'createSession?' + jQuery.param({
			videoId: this.videoId,
			ts: cur_ts
		}) + '&callback=?';
		
		jQuery.getJSON(url, function(json) {
			self.sessionToken = json['token']
		});
		return 0;
	};
	LikeLines.BackendServer.prototype.sendInteractions = function (interactions, forceSend) {
		if (this.readonly) return;
		if (this.baseUrl === undefined) {
			console.log('BackendServer.sendInteractions(): Warning: no back-end specified');
			return;
		}
		
		var self = this;
		var cur_ts = new Date().getTime() / 1000;
		var canSend = this.lastSend+this.options.backendThrottle <= cur_ts;
		
		this.buffer.push.apply(this.buffer, interactions);
		if (this.sessionToken === undefined) {
			return;
		}
		else if (forceSend===true || canSend) {
			this.simplifyBuffer();
			
			var url = this.baseUrl + 'sendInteractions?' + jQuery.param({
				token: this.sessionToken, 
				interactions: JSON.stringify(this.buffer)
			}) + '&callback=?';
			//console.log(cur_ts, url);
			
			jQuery.getJSON(url, function(json) {
				self.buffer = [];
			});
			self.lastSend = cur_ts;
		}
	}
	LikeLines.BackendServer.prototype.simplifyBuffer = function () {
		var newBuffer = [];
		var lastTickEvent = undefined;
		
		// pass 1: remove superfluous ticks
		var n = this.buffer.length;
		for (var i=0; i < n; i++) {
			var evt = this.buffer[i];
			var evtType = evt[1];
			
			if (evtType === 'TICK') {
				lastTickEvent = evt;
			}
			else {
				lastTickEvent = undefined;
				newBuffer.push(evt)
			}
		}
		if (lastTickEvent !== undefined) {
			newBuffer.push(lastTickEvent);
		}
		this.buffer = newBuffer;
		newBuffer = [];
		
		// pass 2: remove superfluous paused events
		var n = this.buffer.length;
		for (var i=0; i < n; i++) {
			var evt = this.buffer[i];
			var evtType = evt[1];
			
			if (evtType === 'PAUSED') {
				if (i===0 || i===n-1) {
					newBuffer.push(evt);
				}
				else if (this.buffer[i-1][1] !== 'PAUSED' || this.buffer[i+1][1] !== 'PAUSED') {
					newBuffer.push(evt);
				}
			}
			else {
				newBuffer.push(evt);
			}
		}
		this.buffer = newBuffer;
	}
	LikeLines.BackendServer.prototype.aggregate = function (callback) {
		if (this.baseUrl === undefined) {
			console.log('BackendServer.aggregate(): Warning: no back-end specified');
			return;
		}
		
		var self = this;
	
		var url = this.baseUrl + 'aggregate?' + jQuery.param({
			videoId: this.videoId
		}) + '&callback=?';
		console.log(url);
		
		jQuery.getJSON(url, function(json) {
			if (callback)
				callback(json);
		});
	}
	
	
	/*--------------------------------------------------------------------*
	 * Utility functions
	 *--------------------------------------------------------------------*/
	LikeLines.Util = {}
	LikeLines.Util.parseQueryString = function (q) {
		var res = {};
		var kv,
		    re_kv = /([^&=]+)=?([^&]*)/g,
		    pluses = /\+/g,
		    decode = function (s) { return decodeURIComponent(s.replace(pluses, " ")); };
		
		while ( kv = re_kv.exec(q) ) {
			res[decode(kv[1])] = decode(kv[2]);
		}
		return res;
	};
	LikeLines.Util.determineVideoSource = function (url) {
		var player, video;
		
		var a = document.createElement('a');
		a.href = url;
		var hostname = a.hostname;
		var query = LikeLines.Util.parseQueryString(a.search.substring(1));
		
		if (hostname == 'youtu.be' || hostname == 'www.youtu.be') {
			player = 'YouTube';
			video = a.pathname.charAt(0) === '/' ? a.pathname.substring(1) : /* IE: */ a.pathname;
		}
		else if (hostname == 'youtube.com' || hostname == 'www.youtube.com') {
			player = 'YouTube';
			video = query['v']; 
		}
		else {
			player = 'HTML5';
			video = url;
		}
		
		var res = {};
		res[player] = video;
		return res;
	};
	LikeLines.Util.merge = function (a, b) {
		var res = {};
		var prop;
		
		for (prop in b)
			res[prop] = b[prop];
		for (prop in a)
			res[prop] = a[prop];
		
		return res;
	};
	LikeLines.Util.kernelSmooth = function (data, weights, K) {
		var n = data.length;
		if (n==0) {
			return function() {return 0;};
		}
		
		if (!K) {
			K = LikeLines.Util.Kernels.gaussian;
		}
		else if (typeof K === 'string') {
			K = LikeLines.Util.Kernels[K];
		}
		
		return (weights === undefined) ? 
			function(x, h) {
				if (!h) {
					h = 1;
				}
				var y = 0;
				for (var i=0; i < n; i++) {
					y += K( (x-data[i])/h );
				}
				y /= n*h;
				return y;
			}
			:
			function(x, h) {
				if (!h) {
					h = 1;
				}
				var y = 0;
				for (var i=0; i < n; i++) {
					y += K( (x-data[i])/h ) * weights[i];
				}
				y /= n*h;
				return y;
			}
	};
	LikeLines.Util.zeros = function (length) {
		var res = [];
		for (var i = 0; i < length; i++) {
			res.push(0);
		}
		return res;
	};
	LikeLines.Util.range = function (length) {
		var res = [];
		for (var i = 0; i < length; i++) {
			res.push(i);
		}
		return res;
	};
	LikeLines.Util.linspace = function (d1, d2, numPoints) {
		var res = [];
		var step = (d2-d1)/(numPoints-1);
		for (var i = 0; i < numPoints-1; i++) {
			res.push(d1 + i*step);
		}
		res.push(d2);
		return res;
	};
	LikeLines.Util.scaleArray = function (data, newSize) {
		var n = (data || []).length;
		var scaledArray;
		
		if (n == 0 || newSize == 0) {
			return LikeLines.Util.zeros(newSize);
		}
		else if (n <= 2) {
			return LikeLines.Util.linspace(data[0], data[n-1], newSize);
		}
		
		// interpolate
		var step = (n-1)/(newSize-1);
		scaledArray = [];
		for (var j = 0; j < newSize-1; j++) {
			var x = j*step;
			var i = Math.floor(x);
			scaledArray[j] = data[i] + (x-i) * (data[i+1] - data[i]);
		}
		scaledArray[newSize-1] = data[n-1];
		
		return scaledArray;
	}
	
	LikeLines.Util.Kernels = {};
	LikeLines.Util.Kernels.gaussian = function (x) {
		return Math.exp(x*x/-2)/Math.sqrt(2 * Math.PI);
	};
	LikeLines.Util.Kernels.tricube = function (x) {
		if (x > 1) {
			return 0;
		}
		else {
			var subexp = (1 - Math.abs(x*x*x));
			return 70/81*subexp*subexp*subexp;
		}
	};
	
	var createPalette = function (/*colorstop, ...*/) {
		var colorstops = Array.prototype.slice.call(arguments);
		var n = colorstops.length;
		
		return function (x) {
			for (var i = 0; i < n; i++) {
				if (x == colorstops[i][0]) {
					return colorstops[i][1];
				} else if (x < colorstops[i][0]) {
					var a = i-1;
					var b = i;
					var c_a = colorstops[a][1];
					var c_b = colorstops[b][1];
					
					var w_a = (colorstops[b][0] - x) / (colorstops[b][0] - colorstops[a][0]);
					var w_b = 1 - w_a;
					
					var res = [0,0,0];
					for (var k=0; k<3; k++) {
						res[k] = Math.round(w_a*c_a[k] + w_b*c_b[k]);
					}
					return res;
				} 
			};
			
			return [0,0,0];
		};
		
	};
	LikeLines.Util.Palettes = {};
	LikeLines.Util.Palettes.heat = createPalette([0.0, [255, 255, 255]],
	                                             [0.2, [255, 255,   0]],
	                                             [1.0, [255,   0,   0]]);
	LikeLines.Util.createPalette = createPalette;
	
})(LikeLines);

