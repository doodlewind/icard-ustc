/**
 * jQuery.fullBg
 * Version 1.0.1
 * Copyright (c) 2012 c.bavota - http://bavotasan.com
 * Dual licensed under MIT and GPL.
 * Date: 10/04/2012
**/
( function($) {
	$.fn.fullBG = function(){
		var el = $(this);

		el.addClass( 'fullBg' );

		function resizeImg() {
			var imgwidth = el.width(),
				imgheight = el.height(),
				winwidth = $(window).width(),
				winheight = $(window).height(),
				heightdiff = winwidth / imgwidth * imgheight,
				new_width = ( heightdiff > winheight ) ? winwidth : winheight / imgheight * imgwidth,
				new_height = ( heightdiff > winheight ) ? winwidth / imgwidth * imgheight : winheight;

			el.css( { 'width' : new_width + 'px', 'height' : new_height + 'px', 'visibility' : 'visible' } );
		}

		$(window).resize( function() {
			resizeImg();
		} ).resize();
	};
} )(jQuery)