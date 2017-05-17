const sampleMetadataRows = [
  "Sample", "Expression Value", "Experiment", "Description",
  "Strain", "Genotype", "Medium (biosynthesis/energy)",
  "Growth setting (planktonic, colony, biofilm)",
  "Growth setting (For planktonic-aerated, static)" +
    "(For biofilms-flow cell, static)",
  "Treatment (drug/small molecule)", "Temperature",
  "Biotic interactor_level 1 (Plant, Human, Bacteria)",
  "Biotic interactor_level 2 (Lung, epithelial cells, " +
    "Staphylococcus aureus, etc)",
  "OD", "Nucleic Acid", "Variant phenotype (QS defective, mucoid, SCV, etc)",
  "Abx marker, auxotrophy", "Additional Notes (markers)", "EXPT SUMMARY",
  "Gene-to-edge odds ratio"
];

function createHeatmap(divId, data, color, min, max) {
  const width = 960;
  const height = 800;
  const cellSize = 25;
  const labelSize = 100;

  const heatmapHeight = cellSize * data.genesY.length;
  const heatmapWidth = cellSize * data.samplesX.length;

  const svg = d3.select(divId).append("svg")
    .attr("width", width)
    .attr("height", height)
    .append("g");

  const container = $("<div style='padding-top: 30px;'>")
    .attr("class","meta col-md-5")
    .addClass("sample-view");

  let bounding;

  function heatmapLegend(heatmapWidth, heatmapHeight) {
    const legendWidth = Math.max(Math.min(heatmapWidth, 500), 100);
    let colorbarLegend = [];
    for (var i = 0; i < legendWidth; i++) { 
      colorbarLegend.push(i / legendWidth); 
    }

    // handles interpolation between expression values and legend position
    var legendScale = d3.scale.linear()
      .domain([min,max])
      .range([0,legendWidth]);
  
    // generates the tick values along the bottom of the legend
    var legendAxis = d3.svg.axis()
      .scale(legendScale)
      .orient("bottom")
      .tickValues(color.domain());

    // a set of single-pixel rectangles are drawn across the legend and
    // colored by their interpolated color value
    svg.append("g")
      .attr("class", "legend axis")
      .attr("transform", "translate(0,-100)")
      .call(legendAxis)
      .selectAll(".legend_cell")
      .data(colorbarLegend)
      .enter().append("rect")
      .attr("x", function(d,i) { return i; })
      .attr("y", -cellSize)
      .attr("width", 1)
      .attr("height", cellSize)
      .attr("fill", function(d) { return color(d); });

    // legend title
    svg.append("text")
       .attr("x", legendWidth / 2)
       .attr("y", -65)
       .attr("text-anchor", "middle")
       .text("normalized expression value");
  }
  
  function heatmap(data, heatmapWidth, heatmapHeight) {
    // holds all of the rectangles in the heatmap
    const cellGroup = svg.append("g");
    const rects = cellGroup.selectAll(".cell")
      .data(data.heatmapData)
      .enter().append("rect")
      .attr("x", function(d) { return d.source_index * cellSize; })
      .attr("y", function(d) { return d.target_index * cellSize; })
      .style("fill", function(d) { return color(d.value); })
      .attr("width", cellSize)
      .attr("height", cellSize)
      .on("mouseover", function(d) {
        const sampleName = data.samplesX[d.source_index];
        console.log(sampleName);
        console.log(data.meta[sampleName]);
        let metadata = data.meta[sampleName];
        if (typeof(metadata) == "string") {
            metadata = JSON.parse(metadata);
        }
        
        let metadataHtml;

        if (!metadata) {
            metadata = {};
        }
        metadata["Expression Value"] = Math.ceil(d.value * 1000.0) / 1000.0;
        metadata["Gene-to-edge odds ratio"] = Math.ceil(
          data.oddsratios[d.target_index] * 1000.0) / 1000.0;
        metadataHtml = "<table class='table table-sm'>" +
          "<thead><tr><th style='width: 30%;'></th>" + 
          "<th style='width: 70%;'></th></tr></thead><tbody>"; 

        for (let i = 0; i < sampleMetadataRows.length; i++) {
            const key = sampleMetadataRows[i];
            if (key in metadata) {
                metadataHtml += "<tr><td style='line-height: 0.9;'><strong>" +
                  key + "</strong></td>" +
                  "<td style='line-height: 0.9;'>" + 
                  metadata[key] + 
                  "</td></tr>";
            }
        }
        metadataHtml += "</tbody>";
        container.html(metadataHtml);
        if (metadataHtml.length != 0) {
          d3.select(this)
            .style("stroke", "black")
            .style("opacity", "0.6");
        }
      })
      .on("mouseout", function(d) {
        d3.select(this)
          .style("opacity", "1")
          .style("stroke", color(d.value));
      })
      .on("click", function(d) {
        const sampleName = data.samplesX[d.source_index];
        const metadata = JSON.parse(data.meta[sampleName]);
        const experiment = metadata["Experiment"];
        const xhr = new XMLHttpRequest();
        window.location.href += "/experiment/" + experiment + "&" +
          divId.substring(1);
      });

    // construct text labels for the y axis
    svg.append("g")
      .attr("class", "y axis")
      .selectAll("text")
      .data(data.genesY)
      .enter().append("text")
      .attr("y", function(d,i) { return i * cellSize + 17.5; })
      .attr("x", -5)
      .attr("text-anchor", "end")
      .attr("fill", function(d, i) {
          const owner = data.ownership[i];
          if (owner == 0) {
              return "pink";
          } else if (owner == 1) {
              return "green";
          } else {
              return "purple";
          }
      })
      .text(function(d) { return d; });

    // construct text labels for the x axis
    svg.append("g")
      .attr("class", "x axis")
      .attr("transform", "translate(0,"+ heatmapHeight +")")
      .selectAll("text")
      .data(data.samplesX)
      .enter().append("text")
      .attr("transform", function(d,i) { 
        var x = (i * cellSize);
        var y = 0;
        return "translate("+ (x + 8) + "," + (y + 5) + ") rotate(90)" ; 
      })
      .text(function(d) { return d; })
      .style("fill", function(d) {
        if ("whitelist" in data) {
          if (data.whitelist.hasOwnProperty("most") 
              && $.inArray(d, data.whitelist.most) > -1) {
              return "red";
          }
          if (data.whitelist.hasOwnProperty("least")
              && $.inArray(d, data.whitelist.least) > -1) {
              return "blue";
          }
        }
        return 'black';
      });

    // title for the x axis
    svg.append("text")
     .attr("x", heatmapWidth / 2)
     .attr("y", -20)
     .attr("text-anchor", "middle")
     .text("Samples");

    // title for the y axis
    svg.append("text")
     .attr("text-anchor", "middle")
     .attr("transform","translate(-150" + "," +
                       (heatmapHeight / 2) +") rotate(90)")
     .text("Genes");
  }
  
  heatmap(data, heatmapWidth, heatmapHeight);
  heatmapLegend(heatmapWidth, heatmapHeight);
  
  bounding = svg.node().getBBox();
  console.log(bounding.x)
  svg.attr("transform", "translate("
                       + bounding.x * -1 + ","
                       + bounding.y * -1 + ")");
  
  d3.select("svg").attr("width", bounding.width);
  d3.select("svg").attr("height", bounding.height);
  return container;
}
