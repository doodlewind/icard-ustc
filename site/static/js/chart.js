var chart = new Object();
chart.barChart = function (testData) {
    nv.addGraph(function () {
        var chart = nv.models.multiBarChart()
                .transitionDuration(350)
                .reduceXTicks(false)   //If 'false', every single x-axis tick label will be rendered.
                .rotateLabels(0)      //Angle to rotate x-axis labels.
                .showControls(true)   //Allow user to switch between 'Grouped' and 'Stacked' mode.
                .groupSpacing(0.1)    //Distance between each group of bars.
                .stacked(true)
            ;

        chart.xAxis
            .tickFormat(function (d) {
                return d;
            });

        chart.yAxis
            .tickFormat(function (d) {
                return d.toFixed(2);
            });

        d3.select('#barChart svg')
            .datum(testData)
            .call(chart);

        nv.utils.windowResize(chart.update);

        return chart;
    });
};

chart.areaChart = function (testData) {
    nv.addGraph(function() {
        var chart = nv.models.stackedAreaChart()
              // .margin({right: 100})
              .x(function(d) { return d[0] })   //We can modify the data accessor functions...
              .y(function(d) { return d[1] })   //...in case your data is formatted differently.
              .useInteractiveGuideline(true)    //Tooltips which show all data points. Very nice!
              .rightAlignYAxis(false)      //Let's move the y-axis to the right side.
              .transitionDuration(500)
              .showControls(false)       //Allow user to choose 'Stacked', 'Stream', 'Expanded' mode.
              .clipEdge(true);

        //Format x-axis labels with custom function.
        chart.xAxis
            .tickFormat(function(d) {
              return d3.time.format('%x')(new Date(d))
        });

        chart.yAxis
            .tickFormat(d3.format(',.2f'));

        d3.select('#areaChart svg')
          .datum(testData)
          .call(chart);

        nv.utils.windowResize(chart.update);

        return chart;
    });
};


chart.areaMonthlyChart = function (testData) {
    nv.addGraph(function () {
        var chart = nv.models.multiBarChart()
                .transitionDuration(350)
                .reduceXTicks(false)
                .rotateLabels(0)
                .showControls(false)
                .groupSpacing(0.1)
                .stacked(true)
                .clipEdge(true);

        chart.xAxis
            .tickFormat(function(d) {
              return d3.time.format('%m月')(new Date(d))
            });

        chart.yAxis
            .tickFormat(function (d) {
                return d.toFixed(2);
            });

        d3.select('#areaMonthlyChart svg')
            .datum(testData)
            .call(chart);

        nv.utils.windowResize(chart.update);

        return chart;
    });
};


chart.pieChart = function (width, height) {
    var testData = $.jStorage.get("pieData", "");

//    var width = 400,
//        height = 400,
    var radius = Math.min(width, height) / 2.5;

    var x = d3.scale.linear()
            .range([0, 2 * Math.PI]);

    var y = d3.scale.linear()
            .range([0, radius]);

    var svg = d3.select("#pieChart").append("svg")
            .attr("width", width)
            .attr("height", height)
        .append("g")
            .attr("transform", "translate(" + width / 2 + "," + (height / 2 + 10) + ")");

    var partition = d3.layout.partition()
            .value(function(d) { return d.size; });

    var arc = d3.svg.arc()
            .startAngle(function(d) { return Math.max(0, Math.min(2 * Math.PI, x(d.x))); })
            .endAngle(function(d) { return Math.max(0, Math.min(2 * Math.PI, x(d.x + d.dx))); })
            .innerRadius(function(d) { return Math.max(0, y(d.y)); })
            .outerRadius(function(d) { return Math.max(0, y(d.y + d.dy)); });

    var g = svg.selectAll("g")
            .data(partition.nodes(testData))
        .enter().append("g");

    var path = g.append("path")
        .attr("d", arc)
        .style("fill", function(d) {
            // modified
            return d.color;
        })
        .on("click", click);

    var text = g.append("text")
        .attr("transform", function(d) { return "rotate(" + computeTextRotation(d) + ")"; })
        .attr("x", function(d) { return y(d.y); })
        .attr("dx", "6") // margin
        .attr("dy", ".35em") // vertical-align
        .text(function(d) {
            if (d.name.split('.').length > 1) {
                return d.name.split('.')[1];
            }
            else return d.name;
        });

    function click(d) {
        // fade out all text elements
        text.transition().attr("opacity", 0);

        path.transition()
            .duration(750)
            .attrTween("d", arcTween(d))
            .each("end", function(e, i) {
                    // check if the animated element's data e lies within the visible angle span given in d
                    if (e.x >= d.x && e.x < (d.x + d.dx)) {
                        // get a selection of the associated text element
                        var arcText = d3.select(this.parentNode).select("text");
                        // fade in the text element and recalculate positions
                        arcText.transition().duration(750)
                            .attr("opacity", 1)
                            .attr("transform", function() { return "rotate(" + computeTextRotation(e) + ")" })
                            .attr("x", function(d) { return y(d.y); });
                    }
            });
    }

    d3.select(self.frameElement).style("height", height + "px");

    // Interpolate the scales!
    function arcTween(d) {
        var xd = d3.interpolate(x.domain(), [d.x, d.x + d.dx]),
                yd = d3.interpolate(y.domain(), [d.y, 1]),
                yr = d3.interpolate(y.range(), [d.y ? 20 : 0, radius]);
        return function(d, i) {
            return i
                    ? function(t) { return arc(d); }
                    : function(t) { x.domain(xd(t)); y.domain(yd(t)).range(yr(t)); return arc(d); };
        };
    }

    function computeTextRotation(d) {
        return (x(d.x + d.dx / 2) - Math.PI / 2) / Math.PI * 180;
    }
};

//d3.select(window).on('resize', pieResize);

function pieResize() {
    // width = parseInt(d3.select('#pieChart').style('width'), 10);
    width = parseInt(d3.select('#pieChart').style('width'), 10);
    $('#pieChart').children().remove();
    chart.pieChart(width-50, width-50);
}