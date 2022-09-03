// the current state
var state = null;
// time where last state has been received
var stateTime = null;
// the currently rendered state
var renderedState = null;
// whether the state has been modified and is updating
var dirtyState = false;
// next key for new recordings
var nextKey = null;
// HTML dict of all recording rows
var rows = {};

const tableUpdateTimeout = 50;

// arguments for all get requests, will be populated by socket.io
var getArgs = '';

function request_update() {
    // block parallel request update calls
    if (typeof request_update.busy === 'undefined' ) {
        request_update.busy = false;
    }

    if (request_update.busy) {
        return;
    }

    request_update.busy = true;
    $.get("/state", getArgs, function(data) {
        update(data);
        request_update.busy = false;
    }).fail(function() {
        request_update.busy = false;
    });
}

function update(data, time=new Date()) {
    if (dirtyState) {
        setTimeout(update, 5, data, time)
    }
    // do not override state with old updates
    if (stateTime >= time) {
        return;
    }
    dirtyState = true;
    state = data
    stateTime = time
    // get new key
    const keys = Object.keys(state.recordings);
    if (keys.length > 0) {
        nextKey = Math.max(...Object.keys(state.recordings).map(Number)) + 1;
    }
    else {
        nextKey = 0;
    }
    updateRecordingsTable();
    dirtyState = false;
}

function createRow(key, recording) {
    const [time, length] = calcRecordingStats(recording);
    var row = document.createElement("tr");
    const progress = `
    <div class="progress" key='${key}' style="height: 2.5em;">
        <div class="progress-bar" role="progressbar" aria-valuenow="${time / length}" aria-valuemin="0" aria-valuemax="1" style="width: ${(time / length) * 100}%;"></div>
    </div>
    `
    row.key = key;
    row.innerHTML = `
        <td style="text-align: center;"></td>
        <td style="text-align: center;"><button type='button' class="btn btn-dark btn-sm" name='loopKeyButton' key='${key}'></button></td>
        <td style="text-align: center;">${progress}</td>
        <td style="text-align: center;"></td>
        <td style="text-align: center;"><form method="get" action="/download/${key}"><button type="submit" class="btn btn-dark btn-sm"><i class="fa fa-download" aria-hidden="true"></i></button></form></td>
        <td style="text-align: center;"><button type='button' class="btn btn-dark btn-sm" name='deleteButton' key='${key}'><i class="fa fa-trash" aria-hidden="true"></i></button>`;
    return $(row);
}

function createFullWidthRow(text) {
    var row = document.createElement("tr");
    row.innerHTML = `<td colspan='9'>${text}</td>`
    return $(row);
}

function updateHTMLifChanged(elem, html) {
    if (elem.html() == html)
        return;

    elem.html(html);
}

function calcRecordingStats(recording) {
    var length = recording.length / state.stream.samplerate;
    var time = recording.frame / state.stream.samplerate;
    if (recording.state == 'record') {
        // get current length
        length += (new Date() - stateTime) / 1000;
    }
    if (recording.state == 'loop') {
        // get current time
        time += (new Date() - stateTime) / 1000;
        time = time % length;
    }
    return [time, length]
}

function updateRecordingsTable() {
    if (state == null) {
        return;
    }

    if (state.stream.active) {
        if (renderedState != null && !renderedState.stream.active) {
            // clear table
            $("#recordings > tbody").html('');
        }
        $("#stream").html(`
            ${state.stream.samplerate} Hz | 
            device ${state.stream.device} |
            ${(state.stream.duration_stats.mean * 1000).toFixed(2)} ± ${(state.stream.duration_stats.std * 1000).toFixed(2)} ms 
            (99p: ${(state.stream.duration_stats['99p'] * 1000).toFixed(2)},
            max: ${(state.stream.duration_stats['max'] * 1000).toFixed(2)})
        `);
    }
    else {
        $("#stream").html(`<b>not active</b>`);
        $("#recordings > tbody").html(createFullWidthRow(state.stream.debug.join("<br>")));
        rows = {};
        return;
    }

    // new keys in the state => add
    var newKeys = [];
    // unused keys in the rows => remove
    var unusedKeys = Object.keys(rows);
    for (const key of Object.keys(state.recordings)) {
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
        rows[key] = createRow(key, state.recordings[key]);
        $("#recordings > tbody").append(rows[key]);
    }

    // update table values
    for (const [key, recording] of Object.entries(state.recordings)) {
        var lastRecording = renderedState == null ? null : renderedState.recordings[key];
        if (typeof lastRecording === 'undefined') {
            lastRecording = null;
        }

        const frameHasUpdated = lastRecording == null || recording.frame != lastRecording.frame || recording.state != lastRecording.state;
        const [time, length] = calcRecordingStats(recording);

        // update values
        var row = rows[key];
        const id = key + (recording.name == '' ? '' : ':' + recording.name);
        updateHTMLifChanged($("td:nth-child(1)", row), `${id}`);
        if (lastRecording == null || lastRecording.state != recording.state) {
            var buttonHTML;
            switch (recording.state) {
                case 'loop':
                    buttonHTML = '<i class="fa fa-pause" aria-hidden="true"></i>';
                    break;
                case 'pause':
                    buttonHTML = '<i class="fa fa-play" aria-hidden="true"></i>';
                    break;
                case 'record':
                    buttonHTML = '<i class="fa fa-microphone" aria-hidden="true"></i>';
                    break;
                default:
                    buttonHTML = '?'
            }
            updateHTMLifChanged($("td > button[name='loopKeyButton']", row), buttonHTML);
        }
        updateHTMLifChanged($("td:nth-child(4)", row), `${length.toFixed(2)}s`);
        var progressBar = $("td:nth-child(3) > .progress > .progress-bar", row);
        const newProgressBarVal = time / length;
        if (recording.state == 'pause' && frameHasUpdated) {
            setProgressBarMode(progressBar, false);
            setProgressBarValue(progressBar, newProgressBarVal, true);
        }
        else if (recording.state == 'loop') {
            setProgressBarMode(progressBar, false);
            setProgressBarValue(progressBar, newProgressBarVal, newProgressBarVal >= progressBar.attr('aria-valuenow'));
        }
        else if (recording.state == 'record') {
            setProgressBarMode(progressBar, true);
        }
    }

    renderedState = state;
}

function setProgressBarValue(progressBar, value, smooth=True) {
    if (smooth) {
        progressBar.css('transition', '');
        progressBar.css('transition-duration', `${tableUpdateTimeout}ms`);
    }
    else {
        progressBar.css('transition', 'none');
    }
    progressBar.css('width', `${value * 100}%`);
    progressBar.attr('aria-valuenow', value);
}

function setProgressBarMode(progressBar, isRecording) {
    if (isRecording) {
        progressBar.addClass('progress-bar-striped bg-success progress-bar-animated');
        setProgressBarValue(progressBar, 1, false);
    }
    else {
        progressBar.removeClass('progress-bar-striped bg-success progress-bar-animated');
    }
}

function setPlaybackTime(key, time) {
    // set frame
    const frame = Math.floor(time * (state.recordings[key].length - 1));
    $.get("/set-frame/" + key + "/" + frame, getArgs, function(data) {
        update(data);
    });
}

$('#recordings').on('click', "tbody > tr > td > button[name='loopKeyButton']", function(e) {
    e.preventDefault();
    const targetKey = $(e.target).closest('button').attr('key');
    loopKey(targetKey);
});

$('#recordings').on('click', "tbody > tr > td > button[name='deleteButton']", function(e) {
    e.preventDefault();
    const targetKey = $(e.target).closest('button').attr('key');
    deleteKey(targetKey);
});

$('#recordings').on('click touchend', "tbody > tr > td > input[type='range']", function(e) {
    e.preventDefault();
    setPlaybackTime($(e.target).attr('key'), $(e.target).val());
});

$('#recordings').on('click', "tbody > tr > td > .progress", function (e) {
    const progressBarDiv = $(e.target).closest('.progress');
    var x = e.pageX - progressBarDiv.offset().left,
        clickedValue = x / progressBarDiv.width();

    setPlaybackTime(progressBarDiv.attr('key'), clickedValue);
});

function loopKey(key) {
    const recordingState = state.recordings[key].state;
    if (recordingState == "pause") {
        $.get("/loop/" + key, getArgs, function(data) {
            update(data);
        });
    }
    else if (recordingState == "loop") {
        $.get("/pause/" + key, getArgs, function(data) {
            update(data);
        });
    }
}

function deleteKey(key) {
    $.get("/delete/" + key, getArgs, function(data) {
        update(data);
    });
}

function pauseAll() {
    $.get("/pause", getArgs, function(data) {
        update(data);
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
                $.get("/poweroff", getArgs, function(data) {});
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

var recordHTML = "Record<br>(<i class=\"fa fa-keyboard-o\"></i> space)"
var recordStopHTML = "Stop Recording<br>(<i class=\"fa fa-keyboard-o\"></i> space)"
$("#record").html(recordHTML);

function recordStart() {
    if (currentRecordingKey != null) {
        return;
    }
    const key = nextKey;
    currentRecordingKey = key;
    var name = $('input[id="recordName"]').val();
    if (typeof name !== "undefined"){
        $('input[id="recordName"]').val("");
    }
    else {
        name = '';
    }

    $.get("/record/" + key, getArgs, function(data) {
        // we started recording
        isRecording = true;
        $("#record").html(recordStopHTML);
        $("#record").removeClass("btn-primary").addClass("btn-success");
        update(data);
        if (name != '') {
            $.get("/set-name/" + key + "/" + name);
        }
    });
}

function recordStop() {
    if (currentRecordingKey == null) {
        return;
    }
    const key = currentRecordingKey;
    const action = loopAfterRecord ? "/loop/" : "/pause/";
    $.get(action + key, getArgs, function(data) {
        // we stopped recording
        isRecording = false;
        $("#record").html(recordHTML);
        $("#record").removeClass("btn-success").addClass("btn-primary");
        update(data);
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
 
if (typeof io !== "undefined") {
    // add websocket functionality and update
    // the state on remote changes
    var socket = io();

    // assign id on connect
    socket.on('connect', function() {
        getArgs = `sid=${socket.id}`;
    });

    // update the state when it is modified by others
    socket.on('update', function(data) {
        update(data);
    });
}

// request updates to keep in sync with the server
// clients without websockets request updates more often as that 
// is their only way to sync with other clients
const updateRequestTimeout = (typeof io !== "undefined") ? 30_000 : 2_500;
setInterval(() => {
    request_update();
}, updateRequestTimeout);

// get the state upon launch
request_update();

// local rendering updates
setInterval(() => {
    updateRecordingsTable();
}, tableUpdateTimeout);