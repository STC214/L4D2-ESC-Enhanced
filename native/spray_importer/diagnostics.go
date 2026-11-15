package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"time"
)

// Diagnostic records contain time/error/path text only, never pixels or source
// payloads. Keep the latest error plus two bounded history files.
func recordFailure(home string, cause error) error {
	if cause == nil {
		return nil
	}
	record := struct{ Time, Version, Error string }{time.Now().Format(time.RFC3339Nano), "1.7.1", cause.Error()}
	latest, err := safePath(home, "logs/last-error.json")
	if err != nil {
		return err
	}
	if err = saveJSON(latest, record); err != nil {
		return err
	}
	path, err := safePath(home, "logs/errors.jsonl")
	if err != nil {
		return err
	}
	line, err := json.Marshal(record)
	if err != nil {
		return err
	}
	line = append(line, '\n')
	const limit = 4 << 20
	stat, err := os.Stat(path)
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	if stat != nil && stat.Size()+int64(len(line)) > limit {
		previous, err := safePath(home, "logs/errors.previous.jsonl")
		if err != nil {
			return err
		}
		// Histories produced here are bounded. Do not read a foreign oversized file.
		if stat.Size() > limit {
			return fmt.Errorf("诊断历史超过 4 MiB；最新错误已写入 %s", latest)
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		if err = atomicWrite(previous, data); err != nil {
			return err
		}
		return atomicWrite(path, line)
	}
	f, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0600)
	if err != nil {
		return err
	}
	n, writeErr := f.Write(line)
	if writeErr == nil && n != len(line) {
		writeErr = io.ErrShortWrite
	}
	if writeErr == nil {
		writeErr = f.Sync()
	}
	closeErr := f.Close()
	if writeErr != nil {
		return writeErr
	}
	if closeErr != nil {
		return closeErr
	}
	return nil
}
