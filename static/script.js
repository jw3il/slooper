var firstLoad = true;
var lastLastState = null;
var lastState = null;
var lastStateTime = null;
var dirtyState = false;
var isUpdating = false;
var nextKey = null;

var recordHTML = "Record<br>(<i class=\"fa fa-keyboard-o\"></i> space)"
var recordStopHTML = "Stop Recording<br>(<i class=\"fa fa-keyboard-o\"></i> space)"
$("#record").html(recordHTML);

var rows = {};

function update() {
    if (isUpdating) {
        return;
    }

    isUpdating = true;
    dirtyState = true;

    // get status and update DOM
    $.get("/status", function(data) {
        lastLastState = lastState;
        lastState = JSON.parse(data);
        lastStateTime = new Date();
        // get new key
        const keys = Object.keys(lastState.recordings);
        if (keys.length > 0) {
            nextKey = Math.max(...Object.keys(lastState.recordings).map(Number)) + 1;
        }
        else {
            nextKey = 0;
        }
        updateRecordingsTable();
        dirtyState = false;
        isUpdating = false;
    }).fail(function() {
        isUpdating = false;
    });
}

function createRow(key) {
    var row = document.createElement("tr");
    row.key = key;
    row.innerHTML = `
        <td></td>
        <td></td>
        <td></td> 
        <td></td>
        <td style="text-align: center;"><input type="range" min="0" max="1" value="0" step="any" key='${key}'></td>
        <td></td>
        <td><input type='button' class="btn btn-dark btn-sm" name='loopKeyButton' key='${key}'></td>
        <td><form method="get" action="/download/${key}"><button type="submit" class="btn btn-dark btn-sm"><i class="fa fa-download" aria-hidden="true"></i></button></form></td>
        <td><button type='button' class="btn btn-dark btn-sm" name='deleteButton' key='${key}'><i class="fa fa-trash" aria-hidden="true"></i></button>`;
    return $(row);
}

function createFullWidthRow(text) {
    var row = document.createElement("tr");
    row.innerHTML = `<td colspan='9'>${text}</td>`
    return $(row);
}

function updateRecordingsTable() {
    if (lastState == null) {
        return;
    }

    if (lastState.stream.active) {
        if (lastLastState != null && !lastLastState.stream.active) {
            // clear table
            $("#recordings > tbody").html('');
        }
        $("#stream").html(`
            ${lastState.stream.samplerate} Hz | 
            device ${lastState.stream.device} |
            ${(lastState.stream.duration_stats.mean * 1000).toFixed(2)} ± ${(lastState.stream.duration_stats.std * 1000).toFixed(2)} ms 
            (99p: ${(lastState.stream.duration_stats['99p'] * 1000).toFixed(2)},
            max: ${(lastState.stream.duration_stats['max'] * 1000).toFixed(2)})
        `);
    }
    else {
        $("#stream").html(`<b>not active</b>`);
        $("#recordings > tbody").html(createFullWidthRow(lastState.stream.debug.join("<br>")));
        rows = {};
        return;
    }

    // new keys in the state => add
    var newKeys = [];
    // unused keys in the rows => remove
    var unusedKeys = Object.keys(rows);
    for (const key of Object.keys(lastState.recordings)) {
        if (key in rows) {
            unusedKeys.splice(unusedKeys.indexOf(key), 1);
        }
        else {
            newKeys.push(key);
        }
    }

    // remove unused rows from DOM
    for (const key of unusedKeys) {
        rows[key].remove();
        delete rows[key];
    }

    // create new rows
    for (const key of newKeys) {
        rows[key] = createRow(key);
        $("#recordings > tbody").append(rows[key]);
    }

    // update table values
    for (const [key, recording] of Object.entries(lastState.recordings)) {
        var length = recording.length / lastState.stream.samplerate;
        var time = recording.frame / lastState.stream.samplerate;
        if (recording.state == 'record') {
            // interpolate length
            length += (new Date() - lastStateTime) / 1000;
        }
        if (recording.state == 'loop') {
            // interpolate time
            time += (new Date() - lastStateTime) / 1000;
            time = time % length;
        }

        // update values
        var row = rows[key];
        const id = key + (recording.name == '' ? '' : ':' + recording.name);
        $("td:nth-child(1)", row).html(`${id}`);
        $("td:nth-child(2)", row).html(`${recording.state}`);
        $("td:nth-child(3)", row).html(`${recording.volume}`);
        $("td:nth-child(4)", row).html(`${time.toFixed(2)}`);
        if (recording.state != 'pause' || firstLoad) {
            $("td:nth-child(5) > input", row).val(time / length);
        }
        $("td:nth-child(6)", row).html(`${length.toFixed(2)}`);
        $("td > input[name='loopKeyButton']", row).val(recording.state == 'loop' ? '⏸' : '▶');
    }

    firstLoad = false;
}

function setPlaybackTime(key, time) {
    // set frame
    const frame = Math.floor(time * (lastState.recordings[key].length - 1));
    $.get("/set-frame/" + key + "/" + frame, function() {
        update();
    });
}

$('#recordings').on('click', "tbody > tr > td > input[name='loopKeyButton']", function(e) {
    e.preventDefault();
    const target = $(e.target);
    loopKey(target.attr('key'));
});

$('#recordings').on('click', "tbody > tr > td > button[name='deleteButton']", function(e) {
    e.preventDefault();
    const target = $(e.target);
    console.log(target);
    deleteKey(target.attr('key'));
});

$('#recordings').on('click', "tbody > tr > td > input[type='range']", function(e) {
    // TODO: Disable animation on hover / click to get desired target value & set slider & frame accordingly
    setPlaybackTime($(e.target).attr('key'), $(e.target).val());
});

function loopKey(key) {
    if (dirtyState) {
        return;
    }

    const state = lastState.recordings[key].state;
    if (state == "pause") {
        $.get("/loop/" + key, function( data ) {
            update();
        });
    }
    else if (state == "loop") {
        $.get("/pause/" + key, function( data ) {
            update();
        });
    }
}

function deleteKey(key) {
    if (dirtyState) {
        return;
    }

    $.get("/delete/" + key, function(data) {
        update();
    });
}

function pauseAll() {
    $.get("/pause", function(data) {
        update();
    });
}

function poweroff() {
    Swal.fire({
        title: 'Shutdown looper',
        text: "Are you sure you want to shut down?",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'No, I am not done yet.',
        cancelButtonText: "Yes, shut down!",
        }).then((result) => {
            if (!result.isConfirmed) {
                $.get("/poweroff", function(data) {});
        }
    })
}

var currentRecordingKey = null;
var loopAfterRecord = false;
var isRecording = false;

$("#record").click(function(){
    if (isRecording) {
        recordStop();
    }
    else {
        loopAfterRecord = ($("#autoLoopCheckbox").is(':checked'));
        recordStart();
    }
});

function recordStart() {
    if (currentRecordingKey != null) {
        return;
    }
    const key = nextKey;
    currentRecordingKey = key;
    const name = $('input[id="recordName"]').val();
    $('input[id="recordName"]').val("");
    // TODO: Error handling...
    $.get("/delete/" + key, function(data) {
        if (name != '') {
            $.get("/set-name/" + key + "/" + name, function() {});
        }
        $.get("/record/" + key, function(data) {
            // we started recording
            isRecording = true;
            $("#record").html(recordStopHTML);
            $("#record").removeClass("btn-primary").addClass("btn-success");
            update();
        });
    });
}

function recordStop() {
    if (currentRecordingKey == null) {
        return;
    }
    const key = currentRecordingKey;
    const action = loopAfterRecord ? "/loop/" : "/pause/";
    $.get(action + key, function(data) {
        // we stopped recording
        isRecording = false;
        $("#record").html(recordHTML);
        $("#record").removeClass("btn-success").addClass("btn-primary");
        update();
        currentRecordingKey = null;
    });
}

$('body').keyup(function(e){
    // space
    if(e.keyCode == 32){
        if (currentRecordingKey == null) {
            loopAfterRecord = true;
            recordStart();
        }
        else {
            recordStop();
        }
    }
});

setInterval(() => {
    updateRecordingsTable();
}, 50);

setInterval(() => {
    update();
}, 2500);
update();
