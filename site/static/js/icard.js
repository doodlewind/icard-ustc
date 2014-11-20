// friendly error tips for "older/newer" button ajax request
$(document).ready(function(){
	onLoad();


	var clickCount = 0;
    // set first fetch time for server
    var fetchStartTime = '2014-09-01';
	$('#background').fullBG();

    // swap their comment status to test
//    $("header").show();
//    $("footer").show();
//    $("#loginBox").hide();
//    $("#mainPanel").show();

	function onLoad() {
        loadScript("http://qzonestyle.gtimg.cn/qzone/app/qzlike/qzopensl.js#jsdate=20111201");
        loadScript("http://widget.renren.com/js/rrshare.js");

        $("#inputId").val($.jStorage.get("id", ""));
        var passwd = $("#inputPassword");
        passwd.val($.jStorage.get("password", ""));

		$("#submitButton").click(loginSubmit);
        $("#refreshBar").click(function(){
            chart.barChart($.jStorage.get("barData", ""));
        });
        $("#refreshArea").click(function(){
            chart.areaChart($.jStorage.get("areaData", ""));
        });
        $("#refreshAreaMonthly").click(function(){
            chart.areaMonthlyChart($.jStorage.get("areaMonthlyData", ""));
        });
        $("#refreshPie").click(function(){
            pieResize();
        });

        $(".nav-brief").click(function(){navSwap("brief")});
        $(".nav-stat").click(function(){
            navSwap("stat");
            setTimeout(function() {
                chart.barChart($.jStorage.get("barData", ""));
                chart.areaChart($.jStorage.get("areaData", ""));
                chart.areaMonthlyChart($.jStorage.get("areaMonthlyData", ""));
            }, 400);

        });
        $(".nav-pie").click(function(){
            navSwap("pie");
            setTimeout(function() {
               pieResize();
            }, 400);
        });
        $(".nav-detail").click(function(){navSwap("detail")});
        $(".nav-config").click(function(){navSwap("config")});

        var newer = $("#newer");
        newer.hide();
        newer.click(function() {
            findDetail($('#startTime').val(), 10, 'newer');
            clickCount --;
            if (clickCount <= 0) {
                $("#newer").hide();
            }
        });
        $("#older").click(function() {
            findDetail($('#endTime').val(), 10, 'older');
            $("#newer").show();
            clickCount ++;
        });

        passwd.focus(function(){
            $("#verifyFailed").hide();
        });

        $("#collapseBtn").click(function(){
            $("#briefPanel").toggle(200);
            setTimeout(function(){$("#collapseOne").toggle(400);}, 200);
        });

        function navSwap(navTag) {
            var bottomIcon = $(".bottom-icon .nav-" + navTag);
            var topIcon = $(".navbar-right .nav-" + navTag);
            topIcon.parent().parent().children().removeClass("active");
            topIcon.parent().addClass("active");
            bottomIcon.parent().children().children().removeClass("fa-2x");
            bottomIcon.children().addClass("fa-2x");
            $("#" + navTag + "Button").trigger("click");
        }

	}

    // login ajax submit
	function loginSubmit() {
        var btn = $("#submitButton");
        btn.attr("disabled", "true");
        btn.text("验证中...");

        var id = $('#inputId').val().toUpperCase();
        var password = $('#inputPassword').val();
        var login_data = {"inputId": id, "inputPassword": password};
        $.ajax({
            type: 'POST',
            url: '/login',
            data: login_data,
            dataType: 'json',

            success: function(json, textStatus) {
                // need to change button status, for browser refresh case
                btn.removeAttr("disabled");
                var userName = json['name'];
                $('#token').val(json['token']);

                switch (userName) {
                    case "王译锋":  userName = "ewind"; break;
                    case "马昊然":  userName = "马神"; break;
                    case "李景昊":  userName = "李神"; break;
                    case "周汪劲":  userName = "汪汪汪"; break;
                    case "王一博":  userName = "博叔"; break;
                    case "王章成":  userName = "章姐姐"; break;
                    case "邓嘉俊":  userName = "俊神"; break;
                    case "邵瞰华":  userName = "邵神"; break;
                    case "张恒若":  userName = "foo"; break;
                    case "高筱培":  userName = "大王"; break;
                    case "陈天朗":  userName = "大王"; break;
                    case "林丰":  userName = "二大王"; break;
                    case "周浩磊":  userName = "粥掌柜"; break;
                    case "陈嘉翔":  userName = "翔总"; break;
                    case "章一超":  userName = "超妹"; break;
                    case "戴一":  userName = "一妹"; break;
                    case "罗浩":  userName = "大副"; break;
                    case "刘楚劼":  userName = "胖子"; break;
                    case "高洋":  userName = "公子"; break;
                    case "张科":  userName = "科长"; break;
                    case "严忠波":  userName = "波波"; break;
                    case "张予曦":  userName = "小师妹"; break;
                    case "周雪翎":  userName = "小小师妹"; break;
                    case "侯宇晖":  userName = "小灰灰"; break;
                    case "徐润雅":  userName = "大喵"; break;
                    case "侯建国":  userName = "校长大人"; break;
                }

                $('#userName').html(userName);
                updateWaitBox(fetchStartTime);

                $("#loginBox").hide(500);
                $("#waitBox").show(500);

                $.jStorage.set("id", id);
                $.jStorage.set("password", password);
                $.jStorage.set("userName", userName);

            },
            error: function(xhr, textStatus, error) {
                btn.removeAttr("disabled");
                btn.text("GO");
            }
        });
	}

    function updateWaitBox(time) {
        var id = $('#inputId').val().toUpperCase();
		var token = $('#token').val();
        var query = {
			"id": id,
			"token": token,
			"time": time
		};
        $.ajax({
            type: 'POST',
            url: '/wait',
            dataType: 'json',
            data: query,

            success: function(data, textStatus) {
                if (data['location'] != 'empty') {
                    $("#waitBar").css("width", progressFromTime(data['time']));
                    $("#waitLocation").html(data['location']);
                    $("#waitDay").html(data['time']);
                    $("#waitAmount").html(data['amount']);
                }

                if (data['end'] == false) {
                    $("#waitText").removeAttr('hidden');
                    updateWaitBox(nextStartTime(data['time']));
                }
                // end fetching and show main panel
                else {
                    $("#waitBar").css("width", '100%');
                    var time = timeToString(new Date());
                    $("header").show(500);
                    $("footer").show(500);
					findDetail(time, 10, 'older');
                    findBrief();
                    findStat();

                    findPie();
                    // get D3.js before main panel show up
                    $("#waitBox").hide(500);
                    loadScript("static/js/d3-compressed.js");
                    loadScript("static/js/chart.js");

                    //load share scripts for qzone

                    $("#mainPanel").show(500);
                }

            },
            error: function(xhr, textStatus, error) {
                // retake if failed
                alert("failed...");
                // setTimeout(updateWaitBox(time), 1000);
            }
        });

        function timeToString(time) {
            var year = time.getFullYear();
            var month = time.getMonth() + 1;
            var date = time.getDate();
            var hour = time.getHours();
            var minute = time.getMinutes();
            var second = time.getSeconds();
            return year + '-' + month + '-' + date + ' ' + hour + ':' + minute + ':' + second;
        }

        function progressFromTime(time) {
             var timeNow = new Date().getTime();
             var timeData = new Date(time).getTime();
             var timeStart = new Date(fetchStartTime).getTime();
             var percent = parseFloat(timeData - timeStart) / parseFloat(timeNow - timeStart);
             percent = parseInt(percent * 100 + 10);
             if (percent > 100) percent = 100;
             else if (percent  < 0) percent = 0;
             return percent + '%';
        }

        function nextStartTime(time) {
            var year = time.split("-")[0];
            var month = time.split("-")[1];
            if (month == '12') {
                year = parseInt(year) + 1;
                month = '01';
            }
            else {
                month = parseInt(month) + 1;
                if (month < 10) {
                    month = "0" + month.toString();
                }
            }
            return year + "-" + month + "-01";
    }

    }

	function findDetail(time, rows, mode) {
		var id = $('#inputId').val().toUpperCase();
		var token = $('#token').val();
		var query = {
			"id": id,
			"token": token,
			// use last record's time to query next page
			"time": time,
			"rows": rows,
			"mode": mode
		};
		$.ajax({
			type: 'POST',
			url: '/detail',
			dataType: 'json',
			data: query,
			beforeSend: function() {
				// alert('sending detail request...');
			},
			success: function(data, textStatus) {
                insertDetail(data);
			},
			error: function(xhr, textStatus, error) {
				alert(textStatus + ', ' + error);
			}
			// timeout: 5000
		});
        function insertDetail(data) {
            // alert(JSON.stringify(data, undefined, 2));
            var len = data.length;
            $('#startTime').val(data[0]['time']);
            $('#endTime').val(data[len - 1]['time']);

            var detailTable = $('#detailTable');
            detailTable.html('');
            for(var i = 0; i < len; i++) {
                var time = data[i]['time'].slice(5, 16);
                var loc = data[i]['location'];
                var amount = data[i]['amount'];
                var html = '<tr><td>' + time + '</td><td>' + loc + '</td><td>' + amount + '</td></tr>';
                detailTable.append(html);
            }
        }
	}

    function findStat() {
        var id = $('#inputId').val().toUpperCase();
		var token = $('#token').val();
        // var id = 'PB12203251';
        // var token = '8184241';
        var query10 = {
			"id": id,
			"token": token,
            "days": 10
		};
        var query60 = {
			"id": id,
			"token": token,
            "days": 60
		};
        var queryMonthly = {
            "id": id,
			"token": token,
            "days": 360
        };

        // stacked bar chart
        $.ajax({
            type: 'POST',
            url: '/stat',
            dataType: 'json',
            data: query10,

            success: function(data, textStatus) {
                data = convertData(data);
                $.jStorage.set("barData", data);
                chart.barChart(data);
            },
            error: function(xhr, textStatus, error) {
                alert("find 10 days record failed...");
            }
        });

        // area chart
        $.ajax({
            type: 'POST',
            url: '/stat',
            dataType: 'json',
            data: query60,

            success: function(data, textStatus) {
                $.jStorage.set("areaData", data);
                chart.areaChart(data);
            },
            error: function(xhr, textStatus, error) {
                alert("find 60 days record failed...");
            }
        });

        // area monthly chart
        $.ajax({
            type: 'POST',
            url: '/stat',
            dataType: 'json',
            data: queryMonthly,

            success: function(data, textStatus) {
                $.jStorage.set("areaMonthlyData", data);
                chart.areaMonthlyChart(data);
            },
            error: function(xhr, textStatus, error) {
                alert("find monthly records failed...");
            }
        });

        function convertTime(time) {
            var year = parseInt(time.split('-')[0]);
            var month = parseInt(time.split('-')[1]);
            var day = parseInt(time.split('-')[2].split(' ')[0]);
            var hour = (parseInt(time.split(' ')[1].split(':')[0]) - 8) % 24;
            var minute = parseInt(time.split(':')[1]);
            var second = parseInt(time.split(':')[2]);
            date = new Date(Date.UTC(year, month, day, hour, minute, second));
            return date;
        }

        function convertData(data) {

            var chartData = [
                {
                    'key': "早",
                    'color': "#D95F49",
                    'values': [
//                        { x: '!', y: 40 },
//                        { x: 4, y: 30 },
//                        { x: 5, y: 20 }
                    ]
                },
                {
                    'key': "午",
                    'color': "#EA9F33",
                    'values': [
//                        { x: '!', y: 60 },
//                        { x: 4, y: 50 },
//                        { x: 5, y: 70 }
                    ]
                },
                {
                    'key': "晚",
                    'color': "#489AD8",
                    'values': [
//                        { x: '!', y: 60 },
//                        { x: 4, y: 50 },
//                        { x: 5, y: 70 }
                    ]
                },
                {
                    'key': "夜",
                    'color': "#54B59A",
                    'values': [
//                        { x: '!', y: 60 },
//                        { x: 4, y: 50 },
//                        { x: 5, y: 70 }
                    ]
                }
            ];
            var end = convertTime(data[0]['time']);
            var start = convertTime(data[data.length - 1]['time']);
            var delta = parseInt((end.getTime() - start.getTime()) / 86400000) + 1;
            var x = start;
            // init empty data object
            for (var i = 0; i < delta; i++) {
                var labelX = x.getDate();
                for (var j = 0; j < 4; j++) {
                    var tmp = {};
                    tmp['x'] = labelX;
                    tmp['y'] = 0.0;
                    chartData[j]['values'].push(tmp);
                }

                x = new Date(x.getTime() + 86400000);
            }
            // alert(JSON.stringify(chartData, undefined, 2));

            for (i = 0; i < data.length; i++) {
                var time = new Date(convertTime(data[i]['time']));
                var hours = time.getHours() ;
                var timeX = time.getDate();
                var amountY = parseFloat(data[i]['amount']);

                if (0 <= hours && hours < 9) {
                    for (j = 0; j < delta; j++) {
                        if (chartData[0]['values'][j]['x'] == timeX) {
                            chartData[0]['values'][j]['y'] += amountY;
                            break;
                        }
                    }
                }
                else if (9 <= hours && hours < 13) {
                    for (j = 0; j < delta; j++) {
                        if (chartData[1]['values'][j]['x'] == timeX) {
                            chartData[1]['values'][j]['y'] += amountY;
                            break;
                        }
                    }
                }
                else if (13 <= hours && hours < 18) {
                    for (j = 0; j < delta; j++) {
                        if (chartData[2]['values'][j]['x'] == timeX) {
                            chartData[2]['values'][j]['y'] += amountY;
                            break;
                        }
                    }
                }
                else {
                   for (j = 0; j < delta; j++) {
                        if (chartData[3]['values'][j]['x'] == timeX) {
                            chartData[3]['values'][j]['y'] += amountY;
                            break;
                        }
                    }
                }

            }
            return chartData;
        }
    }

    function findBrief() {
        var id = $('#inputId').val().toUpperCase();
		var token = $('#token').val();
//        var id = 'PB12203251';
//        var token = '8184241';
        var query = {
			"id": id,
			"token": token
		};
        $.ajax({
            type: 'POST',
            url: '/brief',
            dataType: 'json',
            data: query,

            success: function(data, textStatus) {

                // alert(JSON.stringify(data, undefined, 2));
                $("#thisWeek").html(data['this_week'].toFixed(0));
                $("#thisMonth").html(data['this_month'].toFixed(0));
                $("#lastMonth").html(data['last_month'].toFixed(0));

                var rateType, rate;
                // the richer, the less rate
                if (data['rate'] > 50) {
                    rateType = '节约';
                    rate = data['rate'];

                    $("#rateType").html(rateType);
                    $("#rate").html(data['rate']);
                } else {
                    rateType = '土豪';
                    rate = 100 - data['rate'];

                    $("#rateType").html(rateType);
                    $("#rate").html(100 - data['rate']);
                }

                // register share buttons after rate is done.
                var userName = $.jStorage.get("userName", "");

                // check weixin browser
                if (typeof WeixinJSBridge != "undefined") {
                    document.title = userName + '的' + rateType + '水平击败了' + rate + '%科大人';
                }

                $("#renrenShare").click(function() {
                    var rrShareParam = {
                        resourceUrl : 'http://icard.ustc.edu.cn',
                        srcUrl : '',
                        pic : 'http://icard.ustc.edu.cn/static/img/apple-touch-icon.png',
                        title : userName + '的' + rateType + '水平击败了' + rate + '%科大人！',
                        description : '来自icard.ustc.edu.cn，科大消费数据挖掘站'
                    };
                    rrShareOnclick(rrShareParam);
                });

                $("#weixinShare").click(function() {
                    if (typeof WeixinJSBridge == "undefined") {
                        alert("微信扫码后，即可分享至朋友圈 ^_^");
                        window.open("/static/about.html");
                    }
                    else {
                        document.title = userName + '的' + rateType + '水平击败了' + rate + '%科大人';
                        alert("点击右上角即可分享~");
//                        WeixinJSBridge.invoke('shareTimeline', {
//                            "title": userName + '的' + rateType + '水平击败了' + rate + '%科大人！',
//                            "link": "http://icard.ustc.edu.cn",
//                            "desc": "来自icard.ustc.edu.cn，科大消费数据挖掘站",
//                            "img_url": "http://icard.ustc.edu.cn/static/img/apple-touch-icon.png"
//                        });
                    }
                });

                $("#qzoneShare").attr('href', function() {
                    var p = {
                        url: 'http://icard.ustc.edu.cn',
                        showcount: '0',
                        desc: '',
                        summary: '来自icard.ustc.edu.cn，科大消费数据挖掘站',
                        title: userName + '的' + rateType + '水平击败了' + rate + '%科大人！',
                        site: 'http://icard.ustc.edu.cn',
                        pics: 'http://icard.ustc.edu.cn/static/img/apple-touch-icon.png',
                        style: '202',
                        width: 31,
                        height: 31
                    };
                    var s = [];

                    for (var i in p) {
                        s.push(i + '=' + encodeURIComponent(p[i] || ''));
                    }
                    return 'http://sns.qzone.qq.com/cgi-bin/qzshare/cgi_qzshare_onekey?' + s.join('&');
                });

            },
            error: function(xhr, textStatus, error) {
                alert("find brief failed, please refresh page...");
            }
        });

    }

    function findPie() {
        var data =  $.jStorage.get("pieData", "");
        if (data) {
            return;
        }
        // var id = $('#inputId').val().toUpperCase();
		// var token = $('#token').val();
        var id = 'PB12203251';
        var token = '8184241';
        var query = {
			"id": id,
			"token": token
		};
        $.ajax({
            type: 'POST',
            url: '/pie',
            dataType: 'json',
            data: query,

            success: function(data, textStatus) {
                // alert(JSON.stringify(data, undefined, 2));
                $.jStorage.set("pieData", data);
                $.jStorage.setTTL("pieData", 1000 * 3600 * 24);
                pieResize();
            },
            error: function(xhr, textStatus, error) {
                alert("find pie chart failed, please refresh page...");
            }
        });
    }


    function loadScript(src) {
        var ref = document.createElement('script');
        ref.setAttribute("type","text/javascript");
        ref.setAttribute("src", src);
        if (typeof ref != "undefined")
            document.getElementsByTagName("head")[0].appendChild(ref);
    }

});