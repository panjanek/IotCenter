var ws;
function startWebsocket(wsOnMessage) {
  ws = new WebSocket("wss://"+location.hostname+(location.port ? ':'+location.port: '') + "/ws");
  ws.onmessage = wsOnMessage;
  ws.onclose = function(evt) { 
    console.log("Connection was closed. Reconnecting...");
    setTimeout(startWebsocket(wsOnMessage), 3000);			
  }; 
  
  ws.onopen = function(evt) { console.log('opening websocket') };	  
}    

function showOkMessage(msg) {
  $("#msgOk").html(msg);
  $("#msgOk").slideDown("slow");
  setTimeout(function() { $("#msgOk").slideUp("slow"); }, 5000);      
}

var wsOnMessage = function(evt) { 
      console.log("received:", evt.data);
      msg = JSON.parse(evt.data);
      if(msg.hasOwnProperty("error")) {
          if (msg.error == 123)
              window.location.href = '/login';
      } else {
          if (msg.hasOwnProperty("newImageUrl")) {
              showOkMessage("<p>New image uploaded <a href='"+msg.newImageUrl+"'>here</a></p>");
          }
          
          $("#"+msg.deviceId).effect("highlight", {color:"#1f8dd6"}, 500);            
          $("#"+msg.deviceId+" .last-contact").text(msg.lastContact);
          $("#"+msg.deviceId+" .deviceCommands").show();
          $("#"+msg.deviceId+" .deviceStatus").text("Online");         
          if (msg.hasOwnProperty("values")) {
              for(i=0; i<msg.values.length; i++) {
                  $("#"+msg.deviceId+" .values [data-variable="+msg.values[i].id+"] .sensor-value").text(msg.values[i].value)                       
              }
          }                
      }
  };