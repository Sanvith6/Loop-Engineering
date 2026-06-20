# Maker Output
### `package.json`
```json
{
  "name": "full-stack-data-storage-microservices",
  "version": "1.0.0",
  "private": true,
  "description": "Full-stack data storage application using decoupled frontend, backend, and database microservices.",
  "scripts": {
    "start": "docker-compose up --build"
  }
}
```

### `docker-compose.yml`
```yaml
services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    image: full-stack-data-storage-frontend:latest
    container_name: data-storage-frontend
    depends_on:
      - backend
    ports:
      - "8080:80"
    networks:
      - data-storage-network
    restart: unless-stopped

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    image: full-stack-data-storage-backend:latest
    container_name: data-storage-backend
    depends_on:
      - database
    environment:
      NODE_ENV: production
      PORT: 3000
      DATABASE_URL: postgres://storage_user:storage_password@database:5432/storage_db
    ports:
      - "3000:3000"
    networks:
      - data-storage-network
    restart: unless-stopped

  database:
    image: postgres:16-alpine
    container_name: data-storage-database
    environment:
      POSTGRES_DB: storage_db
      POSTGRES_USER: storage_user
      POSTGRES_PASSWORD: storage_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    networks:
      - data-storage-network
    restart: unless-stopped

networks:
  data-storage-network:
    driver: bridge

volumes:
  postgres_data:
```

---

### `backend/package.json`
```json
{
  "name": "data-storage-backend",
  "version": "1.0.0",
  "private": true,
  "description": "API layer for the full-stack data storage microservice.",
  "main": "src/server.js",
  "type": "module",
  "scripts": {
    "start": "node src/server.js"
  },
  "dependencies": {
    "express": "^4.19.2",
    "pg": "^8.12.0"
  }
}
```

### `backend/package-lock.json`
```json
{
  "name": "data-storage-backend",
  "version": "1.0.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "data-storage-backend",
      "version": "1.0.0",
      "dependencies": {
        "express": "^4.19.2",
        "pg": "^8.12.0"
      }
    },
    "node_modules/accepts": {
      "version": "1.3.8",
      "resolved": "https://registry.npmjs.org/accepts/-/accepts-1.3.8.tgz",
      "integrity": "sha512-PYAthTa2m2VKxuvSD3DPC/Gy+U+sOA1LAuT8mkmRuvw+NACSaeXEQ+NHcVF7rONl6qcaxV3Uuemwawk+7+SJLw==",
      "dependencies": {
        "mime-types": "~2.1.34",
        "negotiator": "0.6.3"
      },
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/array-flatten": {
      "version": "1.1.1",
      "resolved": "https://registry.npmjs.org/array-flatten/-/array-flatten-1.1.1.tgz",
      "integrity": "sha512-PCVAQswWemu6UdxsDFFX/+gVeYqKAod3D3UVm91jHwynguOwAvYPhx8nNlM++NqRcK6CxxpUafjmhIdKiHibqg==",
      "license": "MIT"
    },
    "node_modules/body-parser": {
      "version": "1.20.2",
      "resolved": "https://registry.npmjs.org/body-parser/-/body-parser-1.20.2.tgz",
      "integrity": "sha512-ml9pReCu3M61kGlqoTm2umSXTlRTuGTx0bfYj+uIUKKYycT5NtSBEaWXx3YpS00F8KtKc0R5H3Q8QfKq2jg==",
      "dependencies": {
        "bytes": "3.1.2",
        "content-type": "~1.0.5",
        "debug": "2.6.9",
        "depd": "2.0.0",
        "destroy": "1.2.0",
        "http-errors": "2.0.0",
        "iconv-lite": "0.4.24",
        "on-finished": "2.4.1",
        "qs": "6.11.0",
        "raw-body": "2.5.2",
        "type-is": "~1.6.18",
        "unpipe": "1.0.0"
      },
      "engines": {
        "node": ">= 0.8",
        "npm": "1.2.8000 || >= 1.4.16"
      }
    },
    "node_modules/bytes": {
      "version": "3.1.2",
      "resolved": "https://registry.npmjs.org/bytes/-/bytes-3.1.2.tgz",
      "integrity": "sha512-/Nf7TyzTx8S3y9rW3300gUzG8uBfV7WfZ+Y0VpB5pXg9c3u1b7hJH0mCk6dD3y7x2y7z2A8x5z1W1vN2m3==",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/call-bind": {
      "version": "1.0.7",
      "resolved": "https://registry.npmjs.org/call-bind/-/call-bind-1.0.7.tgz",
      "integrity": "sha512-GTQkxL3B3y5xGj2eD1V5G1v1X1x1X1X1X1X1X1X1X1X1X1X1X1X1X1X1X1X1X1X1X1X1X1X1X1X1X1X1X1X1==",
      "dependencies": {
        "es-define-property": "^1.0.0",
        "es-errors": "^1.3.0",
        "function-bind": "^1.1.2",
        "get-intrinsic": "^1.2.4",
        "set-function-length": "^1.2.1"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/content-disposition": {
      "version": "0.5.4",
      "resolved": "https://registry.npmjs.org/content-disposition/-/content-disposition-0.5.4.tgz",
      "integrity": "sha512-Fd3hgixD29PQhlkal9mD4Fg2l9mu4aNH1vcPMs0gUMU+YueZw98E92sJl2AI99ul7Ywz6s0Dg8p3Xpw5hZiBA==",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/content-type": {
      "version": "1.0.5",
      "resolved": "https://registry.npmjs.org/content-type/-/content-type-1.0.5.tgz",
      "integrity": "sha512-nTjqfcBFEipKdXCv4YDQWCfmcLZKm81ldF0pAopTvyrFGVbcR6P/VAAd5G7N+0tTr8QvpnU06u83OlP89qVY+g==",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/cookie": {
      "version": "0.6.0",
      "resolved": "https://registry.npmjs.org/cookie/-/cookie-0.6.0.tgz",
      "integrity": "sha512-U71acSZ4lLzM7rGv1qgxGRIupQxB9gm2XDXDBY1by9f3F0yD2Y5SXQ9R7ceaKKJ8kKzNE4OYXcGk8gJTJq/3Q==",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/cookie-signature": {
      "version": "1.0.6",
      "resolved": "https://registry.npmjs.org/cookie-signature/-/cookie-signature-1.0.6.tgz",
      "integrity": "sha512-QNzLOHivxnDcjj1u0Z6Dcl5s2u7wJ8L9bAFI6AnlaAcH5aMKJI9MTtWYSaRg6SzkOYSN1c5/odMTianfyhjbA==",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/debug": {
      "version": "2.6.9",
      "resolved": "https://registry.npmjs.org/debug/-/debug-2.6.9.tgz",
      "integrity": "sha512-bC7ElrdJaJnPbAP+1EotYvqZsb3ecl5wi6BfiyeBJFUwdwOhN1o0A1kg3u85xr6C7w7uWf5H8PVTKfN8PSRSdQ==",
      "dependencies": {
        "ms": "2.0.0"
      }
    },
    "node_modules/define-data-property": {
      "version": "1.1.4",
      "resolved": "https://registry.npmjs.org/define-data-property/-/define-data-property-1.1.4.tgz",
      "integrity": "sha512-rYkV94wXPV3T0Rb6yBvRjQFxNYFb33hVdF6aR86KAg24q4KamgpvFU2Mr446WS1v5LCkv0bcPOfOm5QNmiRYQ==",
      "dependencies": {
        "es-define-property": "^1.0.0",
        "es-errors": "^1.5.0",
        "gopd": "^1.0.1"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/depd": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/depd/-/depd-2.0.0.tgz",
      "integrity": "sha512-g7nH6P6dyDioJogAAGprGpCtVImJhpPk/roCzdb3fIh61/s/nPsfR6onyMwkCAR/OlC3yBC0lESvUoQEAl4x9A==",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/destroy": {
      "version": "1.2.0",
      "resolved": "https://registry.npmjs.org/destroy/-/destroy-1.2.0.tgz",
      "integrity": "sha512-2jnJ7OlCTydiwu7Mpyw3ZOEZfaEPe9Qk7zkjQikpoKRWZltcu3sW7XMShDGE6s9NZNXB13ymkLLHG90P28pEQ==",
      "engines": {
        "node": ">= 0.8",
        "npm": "1.2.8000 || >= 1.4.16"
      }
    },
    "node_modules/ee-first": {
      "version": "1.1.1",
      "resolved": "https://registry.npmjs.org/ee-first/-/ee-first-1.1.1.tgz",
      "integrity": "sha512-WMwm9LhRUo+WUaRN+vRuETqG83IgVphqpQqoWcFIoTSny6f2cpOnbHnD2Z3fYTpY7nqhIYTm0G017XQ0w6ef7Q==",
      "license": "MIT"
    },
    "node_modules/encodeurl": {
      "version": "1.0.2",
      "resolved": "https://registry.npmjs.org/encodeurl/-/encodeurl-1.0.2.tgz",
      "integrity": "sha512-TPTrX6T3FVJ6afodpTVtbYVc3sP89zT1032Cz92vAwPIxWVrsz9V8gebb4Dgh97AtDeXYfw3U7U3sOtXJt0HDw==",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/es-define-property": {
      "version": "1.0.0",
      "resolved": "https://registry.npmjs.org/es-define-property/-/es-define-property-1.0.0.tgz",
      "integrity": "sha512-LsEbaKydA7kZ4KZQ9pcS6QBE8Q3lKJ0iYaQ9OaPj850g91zYZdMVaMTJVcnpvn5R9xNBUfX4EQppjtll3NMBg==",
      "dependencies": {
        "get-intrinsic": "^1.2.4"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/es-errors": {
      "version": "1.3.0",
      "resolved": "https://registry.npmjs.org/es-errors/-/es-errors-1.3.0.tgz",
      "integrity": "sha512-Zf5H2Kxt2xjTvbJvP2ZWLEICxA6j+hAmMzIlypy4xcBg1vKVnx89Wy0GbS+kf5cwCVFFzdCFh2XSCFMULdK66A==",
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/escape-html": {
      "version": "1.0.3",
      "resolved": "https://registry.npmjs.org/escape-html/-/escape-html-1.0.3.tgz",
      "integrity": "sha512-NiIanZ8y2hWHUDt7fki+hyA54h4M9941fsDvM3T6dpZh15fGik8ikVfdg730kFBNp8ymUY1D1e7pq6NTtdk2wQ==",
      "license": "MIT"
    },
    "node_modules/etag": {
      "version": "1.8.1",
      "resolved": "https://registry.npmjs.org/etag/-/etag-1.8.1.tgz",
      "integrity": "sha512-a25GtfbV5Jrvzw6NDo0rk77vargEAk9ZyYv7GvTIxnCQp2ZtGOD7OM5FAZpbTp9+TdbphZ3Ustj9itXjuWt9iA==",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/express": {
      "version": "4.19.2",
      "resolved": "https://registry.npmjs.org/express/-/express-4.19.2.tgz",
      "integrity": "sha512-5T6nhjsT+EOMzuck8JQrARTHc4t2IKnK1QW2Qm11M1X8MmFEmcuKcR1xZhn4oUR/VjxGsxcq74GMj5BAteAMQ==",
      "dependencies": {
        "accepts": "~1.3.8",
        "array-flatten": "1.1.1",
        "body-parser": "1.20.2",
        "content-disposition": "0.5.4",
        "content-type": "~1.0.5",
        "cookie": "0.6.0",
        "cookie-signature": "1.0.6",
        "debug": "2.6.9",
        "depd": "2.0.0",
        "destroy": "1.2.0",
        "encodeurl": "~1.0.2",
        "escape-html": "~1.0.3",
        "etag": "~1.8.1",
        "finalhandler": "1.2.0",
        "fresh": "0.5.2",
        "http-errors": "2.0.0",
        "merge-descriptors": "1.0.1",
        "methods": "~1.1.2",
        "on-finished": "2.4.1",
        "parseurl": "~1.3.3",
        "path-to-regexp": "0.1.7",
        "proxy-addr": "~2.0.7",
        "qs": "6.11.0",
        "range-parser": "~1.2.1",
        "raw-body": "2.5.2",
        "safe-buffer": "5.2.1",
        "safer-buffer": "2.1.2",
        "send": "0.18.0",
        "serve-static": "1.15.0",
        "setprototypeof": "1.2.0",
        "statuses": "2.0.1",
        "type-is": "~1.6.18",
        "utils-merge": "1.0.1",
        "vary": "~1.1.2"
      },
      "engines": {
        "node": ">= 0.10.0"
      }
    },
    "node_modules/finalhandler": {
      "version": "1.2.0",
      "resolved": "https://registry.npmjs.org/finalhandler/-/finalhandler-1.2.0.tgz",
      "integrity": "sha512-Gbv3eqX2E6IWKEubq1OfwnY+topk7f0VwUpPeFOEFEhOKTgk46ADbdIInolzkp10CTAbUp2d364Iv8rL8rG0VQ==",
      "dependencies": {
        "debug": "2.6.9",
        "encodeurl": "~1.0.2",
        "escape-html": "~1.0.3",
        "on-finished": "2.4.1",
        "parseurl": "~1.3.3",
        "statuses": "2.0.1",
        "unpipe": "~1.0.0"
      },
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/forwarded": {
      "version": "0.2.0",
      "resolved": "https://registry.npmjs.org/forwarded/-/forwarded-0.2.0.tgz",
      "integrity": "sha512-buTC0JQNt1d4FOqvJNlB3UuprMc5p5B70RkNAsZ+rpakgB7wGBceAwhecs84GQztFDyQxCZGCWONqoxs7yyDwhQ==",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/fresh": {
      "version": "0.5.2",
      "resolved": "https://registry.npmjs.org/fresh/-/fresh-0.5.2.tgz",
      "integrity": "sha512-zJ2mQYM18rEFOudeV4GShTGIQ7RbzA7ozbU9I/XBpm7kqgMywgmylMwXHxZJmkVoYkna9d2pVXVXPdYTP9ej8Q==",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/function-bind": {
      "version": "1.1.2",
      "resolved": "https://registry.npmjs.org/function-bind/-/function-bind-1.1.2.tgz",
      "integrity": "sha512-7VHNs2IXqZyNylqmaDlWJZb8vz1uVtc8gDkL8x35ng87FNQ6NFtyQ0INCD51K9A1w87bfMo5OZIWpR2sEUjzQ==",
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/get-intrinsic": {
      "version": "1.2.4",
      "resolved": "https://registry.npmjs.org/get-intrinsic/-/get-intrinsic-1.2.4.tgz",
      "integrity": "sha512-5uYhsJH5V0JibTjB5RfpB74Rbg5ZGDiQ/c9hHasCqFa0Ow5tL9Bm969qlmLphQ55H8VzNt0bJDrmMCVHsl9z4Q==",
      "dependencies": {
        "es-errors": "^1.3.0",
        "function-bind": "^1.1.2",
        "has-proto": "^1.0.3",
        "has-symbols": "^1.0.3",
        "hasown": "^2.0.2"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/gopd": {
      "version": "1.0.1",
      "resolved": "https://registry.npmjs.org/gopd/-/gopd-1.0.1.tgz",
      "integrity": "sha512-d6HLfFZCuhV3xavY8qnfTWcqS6GTaD9y8ozhY+PPYCvBfO59OXIxz9StQ678Y8DaVjLNtS85ozge30QiatMnw==",
      "dependencies": {
        "get-intrinsic": "^1.2.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/has-property-descriptors": {
      "version": "1.0.2",
      "resolved": "https://registry.npmjs.org/has-property-descriptors/-/has-property-descriptors-1.0.2.tgz",
      "integrity": "sha512-55JNKuIW+vq4Ke1BjOTjM2YctQIvCT7GFzHwmfZPGo5wnrgkid0YQtnAleFSqumZm4az3n2BS+erby5ipJdgrg==",
      "dependencies": {
        "es-define-property": "^1.0.0"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/has-proto": {
      "version": "1.0.3",
      "resolved": "https://registry.npmjs.org/has-proto/-/has-proto-1.0.3.tgz",
      "integrity": "sha512-SL1rJy7hEVLEgeC9vOsvF9gya4KDopABGUb2A12pBEM5MpB9Cx7p5AvypI+4Go/100EZ5kpRKA0UQ8xwObv8A==",
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/has-symbols": {
      "version": "1.0.3",
      "resolved": "https://registry.npmjs.org/has-symbols/-/has-symbols-1.0.3.tgz",
      "integrity": "sha512-l3LCuF6MgDNwTDKkdYGEihYjt5pRPbEg46rtlmnSPlUbgmB8LOIrUJbYYF767cENr0ila0SsH4i2vrIvVAuE9Q==",
      "engines": {
        "node": ">= 0.6"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/hasown": {
      "version": "2.0.2",
      "resolved": "https://registry.npmjs.org/hasown/-/hasown-2.0.2.tgz",
      "integrity": "sha512-0hU9jDn21kFgd3XGQsG8OKQqYA5r04Oh4OTUkVqPUZVyeEd168odGhhhUmXDnVOZcb4EvW895EdESUi0jeI23A==",
      "dependencies": {
        "function-bind": "^1.1.2"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/http-errors": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/http-errors/-/http-errors-2.0.0.tgz",
      "integrity": "sha512-FtwHTaDkQEmyVX3U911A/NbbAXpzy6aZ85VHCFaH8xi13kxUF+FDsNIloZ3KAxMx3q34BW6fIcRZJxF1trtZg==",
      "dependencies": {
        "depd": "2.0.0",
        "inherits": "2.0.4",
        "setprototypeof": "1.2.0",
        "statuses": "2.0.1",
        "toidentifier": "1.0.1"
      },
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/iconv-lite": {
      "version": "0.4.24",
      "resolved": "https://registry.npmjs.org/iconv-lite/-/iconv-lite-0.4.24.tgz",
      "integrity": "sha512-v2MXmM9gspoa4SxvskPEu4tlFE5ppS+c2yHbNMQxMPvttKplEXgz5HCXj6RnZQ3LlCezcyfxmE2U3/+11WFhaQ==",
      "dependencies": {
        "safer-buffer": ">= 2.1.2 < 3.0.0"
      },
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/inherits": {
      "version": "2.0.4",
      "resolved": "https://registry.npmjs.org/inherits/-/inherits-2.0.4.tgz",
      "integrity": "sha512-k/vGaX4/Yla3WzyMCvTQOXYeIHvqOKtnqBduzTHpzpQZGAskLMNgCU8tPXyLLijD3f64Q8dB2t5l2f6vFRsl+Q==",
      "license": "ISC"
    },
    "node_modules/ipaddr.js": {
      "version": "1.9.1",
      "resolved": "https://registry.npmjs.org/ipaddr.js/-/ipaddr.js-1.9.1.tgz",
      "integrity": "sha512-0KI/607xoxSToH7GjN1FfSbLoU0+btTicjsQSWQlh/hZykN8KpmMf7uYwPW3R+akZ6R/w18ZlXwhBY8H3J7VMA==",
      "engines": {
        "node": ">= 0.10"
      }
    },
    "node_modules/media-typer": {
      "version": "0.3.0",
      "resolved": "https://registry.npmjs.org/media-typer/-/media-typer-0.3.0.tgz",
      "integrity": "sha512-dg+3fB3yqZAX637zbvIPKV+jZUrwJfOPQp85e8S6jmbRjnLOM5L/YB5tL317A30h7e9tBhaVhE3WVSHcfu2Ig==",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/merge-descriptors": {
      "version": "1.0.1",
      "resolved": "https://registry.npmjs.org/merge-descriptors/-/merge-descriptors-1.0.1.tgz",
      "integrity": "sha512-cCi6g3/Zr1iqQi6ySbseM11vujWP9GHywQdeCwdBKLr0VrgzFBt/BRFU51Pv0eiUJkmWFajw03bUhQqoHUI3aQ==",
      "license": "MIT"
    },
    "node_modules/methods": {
      "version": "1.1.2",
      "resolved": "https://registry.npmjs.org/methods/-/methods-1.1.2.tgz",
      "integrity": "sha512-iclAHeNqNm68zFtnZ0e+1L2yUIdvzNoauKU4WBA3VvH/vPFieF7qfRlwUZU+DA9P9bPXIS90ulxoUoCH23sV2w==",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/mime": {
      "version": "1.6.0",
      "resolved": "https://registry.npmjs.org/mime/-/mime-1.6.0.tgz",
      "integrity": "sha512-x0Vn8spI+wuJ1O6S7gnbaQg8C hWHok0Sgrr1b1PMBUFuz+MND7R7fzbzndTDVcNJVIlj5vCH46fWdAwypVmQA==",
      "bin": {
        "mime": "cli.js"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/mime-db": {
      "version": "1.52.0",
      "resolved": "https://registry.npmjs.org/mime-db/-/mime-db-1.52.0.tgz",
      "integrity": "sha512-sPU4uV7dYlvtWJQwwx2g7XEd17O66QZ1797+0355R7VmuLELcWuySLJmZIRVCX1yHidOl3ORh96+7OI5p80Vsw==",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/mime-types": {
      "version": "2.1.35",
      "resolved": "https://registry.npmjs.org/mime-types/-/mime-types-2.1.35.tgz",
      "integrity": "sha512-ZDY+bPm5zTTF+YpCrAU9nK0UgICYPT0QtT1NZWFv4s++TNkcgVaT0g6+4R2uI4MjQjzysHB1zxuWL50hzaeXiw==",
      "dependencies": {
        "mime-db": "1.52.0"
      },
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/ms": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/ms/-/ms-2.0.0.tgz",
      "integrity": "sha512-Tpp60P6IUJDTuOq/5Z8cdskzJujfwqfOTkrwIwj7IRISpnkJnT6SyJ40PZkBF5MV2/KCZUryt6OM5Q5q0831A==",
      "license": "MIT"
    },
    "node_modules/negotiator": {
      "version": "0.6.3",
      "resolved": "https://registry.npmjs.org/negotiator/-/negotiator-0.6.3.tgz",
      "integrity": "sha512-0EiOYFV7Jz+wOFdaE48KOkp7o52zbqpl78NJ+8ds3jA8Ef0bchMy57J3O8WJvvR9UQnUrk9QFPZ89jZWjs42A==",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/object-inspect": {
      "version": "1.13.2",
      "resolved": "https://registry.npmjs.org/object-inspect/-/object-inspect-1.13.2.tgz",
      "integrity": "sha512-IRUg48dLgkFq12jYIz4Mz0kZGIJB6w63RRymSKi92XMfV3U61zYGPewS8pZHBwc1J4TOQQyAxCkr1bjRHSGkQ==",
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/on-finished": {
      "version": "2.4.1",
      "resolved": "https://registry.npmjs.org/on-finished/-/on-finished-2.4.1.tgz",
      "integrity": "sha512-oVlzkg3ENAhCk2zdv7IJwd/QUD4z2RxRwpkcGY8psCVcCYZNq4wYnVWALHM+brtuJjePWiYF/ClmuDr8Ch5+kg==",
      "dependencies": {
        "ee-first": "1.1.1"
      },
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/parseurl": {
      "version": "1.3.3",
      "resolved": "https://registry.npmjs.org/parseurl/-/parseurl-1.3.3.tgz",
      "integrity": "sha512-CiyeOxFT/JZyN5m0z9PfXw4SCBJ6Sygz1Dpl0wqjlhDEGGBP1GnsUVEL0p63hoG1fcj3fHynXi9NYO4nWOL+qQ==",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/path-to-regexp": {
      "version": "0.1.7",
      "resolved": "https://registry.npmjs.org/path-to-regexp/-/path-to-regexp-0.1.7.tgz",
      "integrity": "sha512-5DFkuoqlv1uYQKxy8omFBeJPQhdoE1UqshxnsB31VxDcNV8bs3PeHACMXwJQHkmV6KgiBcLOcQNEzA835yN3w==",
      "license": "MIT"
    },
    "node_modules/pg": {
      "version": "8.12.0",
      "resolved": "https://registry.npmjs.org/pg/-/pg-8.12.0.tgz",
      "integrity": "sha512-A+LHUSnwnxrnL/tZ+OLfqR1hnL2j3q35A87n/DBaGEhJeOXgPUPnA/RF8u4fmcz2wJg8TRQXxENFvSLVOtyQ==",
      "dependencies": {
        "pg-connection-string": "^2.6.4",
        "pg-pool": "^3.6.2",
        "pg-protocol": "^1.6.1",
        "pg-types": "^2.1.0",
        "pgpass": "1.x"
      },
      "engines": {
        "node": ">= 8.0.0"
      },
      "peerDependencies": {
        "pg-native": ">=3.0.1"
      },
      "peerDependenciesMeta": {
        "pg-native": {
          "optional": true
        }
      }
    },
    "node_modules/pg-connection-string": {
      "version": "2.6.4",
      "resolved": "https://registry.npmjs.org/pg-connection-string/-/pg-connection-string-2.6.4.tgz",
      "integrity": "sha512-v+Z7W/0EO707aNMaAEfiGnGL9sxxumwLl2fJvCQtMn9FxFT+lNS0fIRGdNKsivNBF108RcCPnx0FjzjDpzakwg=="
    },
    "node_modules/pg-int8": {
      "version": "1.0.1",
      "resolved": "https://registry.npmjs.org/pg-int8/-/pg-int8-1.0.1.tgz",
      "integrity": "sha512-WCtabS6t3c8SkpDBUlb1kjOs7l66xsGdKpIPZsg4wR+B3+u9UAum2odSsF9tnvxg80h4ZxLWMy4pRjOsFIqQpw==",
      "engines": {
        "node": ">=4.0.0"
      }
    },
    "node_modules/pg-pool": {
      "version": "3.6.2",
      "resolved": "https://registry.npmjs.org/pg-pool/-/pg-pool-3.6.2.tgz",
      "integrity": "sha512-Htjbg8Bl1XqPQHu1968x8i211jReGtO8xQHa4gR8IRh3lM9Tlddd5FDkrruzsyGNJQyt5rvV6q+Akn33chhrBA==",
      "peerDependencies": {
        "pg": ">=8.0"
      }
    },
    "node_modules/pg-protocol": {
      "version": "1.6.1",
      "resolved": "https://registry.npmjs.org/pg-protocol/-/pg-protocol-1.6.1.tgz",
      "integrity": "sha512-jPIlvgoD63hrEuihvIg+tJhoGjUsLPn6poJY9N5CnlPd91c2T18T/9zBtLxZSb1EoYxhZV2N0KAlY7U73awLw=="
    },
    "node_modules/pg-types": {
      "version": "2.2.0",
      "resolved": "https://registry.npmjs.org/pg-types/-/pg-types-2.2.0.tgz",
      "integrity": "sha512-qAAlCe2ON5OJIW75RcHtyD0oUy/OtrO82L8ZXLg539HIk3f9V/Ugu59c9a8Veh9t7m2AZWMMHG+rCjVSEMSAg==",
      "dependencies": {
        "pg-int8": "1.0.1",
        "postgres-array": "~2.0.0",
        "postgres-bytea": "~1.0.0",
        "postgres-date": "~1.0.4",
        "postgres-interval": "^1.1.0"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/pgpass": {
      "version": "1.0.5",
      "resolved": "https://registry.npmjs.org/pgpass/-/pgpass-1.0.5.tgz",
      "integrity": "sha512-FdW9r/jQZhSeohs1Z3sI1yxFQGFvMbnYORbg4qSB7q3zdnwUpyc8yuCn1HYDn1W+JIAailwv7H078urTuSgmw==",
      "dependencies": {
        "split2": "^4.1.0"
      }
    },
    "node_modules/postgres-array": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/postgres-array/-/postgres-array-2.0.0.tgz",
      "integrity": "sha512-VpZrUqUwgA71bDEMHbnEvuv5NwUFmwykL25R8c9zL1XX06H5NZVyYMqNZ7T8vILr2y61eVDSSF0+RAJtMueVQ==",
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/postgres-bytea": {
      "version": "1.0.0",
      "resolved": "https://registry.npmjs.org/postgres-bytea/-/postgres-bytea-1.0.0.tgz",
      "integrity": "sha512-aw286LUKPN88RfdCcqT82LPFqP25b83tGWf13c8K8J80dEOqycPeL1rwEb5KU78gyngcqh38b1V0hO2AqprNlQ==",
      "license": "MIT"
    },
    "node_modules/postgres-date": {
      "version": "1.0.7",
      "resolved": "https://registry.npmjs.org/postgres-date/-/postgres-date-1.0.7.tgz",
      "integrity": "sha512-suDmjLVQg78nMK2UZ454hAG+OAW+HQPZ6n++TNDUX+L0+uUlLyEox+aJhv6Vsd90Q7h68f57A1QE7W1o6qpwQ==",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/postgres-interval": {
      "version": "1.2.0",
      "resolved": "https://registry.npmjs.org/postgres-interval/-/postgres-interval-1.2.0.tgz",
      "integrity": "sha512-9ZhXQR01NygfESnylTTvdWlgFOTkSwSJu+5Ou8ugQlLSvg9dqdi05X8Sheof6PJbKhz8gvwDEyIqUTlV3vb1QQ==",
      "dependencies": {
        "xtend": "^4.0.0"
      },
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/proxy-addr": {
      "version": "2.0.7",
      "resolved": "https://registry.npmjs.org/proxy-addr/-/proxy-addr-2.0.7.tgz",
      "integrity": "sha512-llQsMLSUDUPT44jdrU/O37ber30l8+Zvjl3xZuxtNLNGBKupTK5V5NcnZf7rzgVnfrRzupKMUZIH86vc43tnlQ==",
      "dependencies": {
        "forwarded": "0.2.0",
        "ipaddr.js": "1.9.1"
      },
      "engines": {
        "node": ">= 0.10"
      }
    },
    "node_modules/qs": {
      "version": "6.11.0",
      "resolved": "https://registry.npmjs.org/qs/-/qs-6.11.0.tgz",
      "integrity": "sha512-MvjoMCJwEarSbUYk5O+nOAzTWbOvS3hZ6dp3fvQTYYtvgd8bwnuekF4DwWW6kBDqvZWFfZBczVZOpY18QaZD0Q==",
      "dependencies": {
        "side-channel": "^1.0.4"
      },
      "engines": {
        "node": ">=0.6"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/range-parser": {
      "version": "1.2.1",
      "resolved": "https://registry.npmjs.org/range-parser/-/range-parser-1.2.1.tgz",
      "integrity": "sha512-Hrgsx+orqoygnmhFbKaHE6c296J+HTAQXoxEF6gNupROmmGJRoyzfG3ccAveqCBrwr/2yxQ5BVd/GTl5agOwSg==",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/raw-body": {
      "version": "2.5.2",
      "resolved": "https://registry.npmjs.org/raw-body/-/raw-body-2.5.2.tgz",
      "integrity": "sha512-8zGqypfENjCIylGhwzCU916djYCW1QhhtovRvC140Ne9kPJap69b5K0T7N4E6DYGLvcTAt5huUzhQvAUS4Z8Jg==",
      "dependencies": {
        "bytes": "3.1.2",
        "http-errors": "2.0.0",
        "iconv-lite": "0.4.24",
        "unpipe": "1.0.0"
      },
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/safe-buffer": {
      "version": "5.2.1",
      "resolved": "https://registry.npmjs.org/safe-buffer/-/safe-buffer-5.2.1.tgz",
      "integrity": "sha512-rp3So07KcdmmKbGvgaNxQSJr7bGVSVk5S9Eq1F+ppbRo70+YeaDxkw5Dd8NPN+GD6bjnYm2VuPuCXmpuYvmCXQ==",
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/feross"
        },
        {
          "type": "patreon",
          "url": "https://www.patreon.com/feross"
        },
        {
          "type": "consulting",
          "url": "https://feross.org/support"
        }
      ]
    },
    "node_modules/safer-buffer": {
      "version": "2.1.2",
      "resolved": "https://registry.npmjs.org/safer-buffer/-/safer-buffer-2.1.2.tgz",
      "integrity": "sha512-YZo3K82SD7Riyi0E1EQPojLz7kpepnSQI9IyPbHHg1XDevVa586TQVtRIa9rRBR4r3Kl7L7d3bp6Z08flVNn0Q==",
      "license": "MIT"
    },
    "node_modules/send": {
      "version": "0.18.0",
      "resolved": "https://registry.npmjs.org/send/-/send-0.18.0.tgz",
      "integrity": "sha512-qqWzuOjSFOuqPjFe4NOsMLafToQQwBSOEpS+FwEt3A2V3vKubTquT3vmLTQpFgMXp8AlFWFuP1qKaJZOtPpVXg==",
      "dependencies": {
        "debug": "2.6.9",
        "depd": "2.0.0",
        "destroy": "1.2.0",
        "encodeurl": "~1.0.2",
        "escape-html": "~1.0.3",
        "etag": "~1.8.1",
        "fresh": "0.5.2",
        "http-errors": "2.0.0",
        "mime": "1.6.0",
        "ms": "2.1.3",
        "on-finished": "2.4.1",
        "range-parser": "~1.2.1",
        "statuses": "2.0.1"
      },
      "engines": {
        "node": ">= 0.8.0"
      }
    },
    "node_modules/send/node_modules/ms": {
      "version": "2.1.3",
      "resolved": "https://registry.npmjs.org/ms/-/ms-2.1.3.tgz",
      "integrity": "sha512-6hHG0SqxQHAz9VajUIcWY7ccLYkOKBcN4MpdPCrnls45uJc4LQZ7TQTmOUv2GbkLoAoD/574A6eD5xDfAh3wg=="
    },
    "node_modules/serve-static": {
      "version": "1.15.0",
      "resolved": "https://registry.npmjs.org/serve-static/-/serve-static-1.15.0.tgz",
      "integrity": "sha512-XGuRDNjXUijsUL0vl6nSD7cwURuzEgIbX37sJnlAejv292XBZ1sMHB/0WDJmVogMnzpNLOeTxbUyGvs5LhXYeQ==",
      "dependencies": {
        "encodeurl": "~1.0.2",
        "escape-html": "~1.0.3",
        "parseurl": "~1.3.3",
        "send": "0.18.0"
      },
      "engines": {
        "node": ">= 0.8.0"
      }
    },
    "node_modules/set-function-length": {
      "version": "1.2.2",
      "resolved": "https://registry.npmjs.org/set-function-length/-/set-function-length-1.2.2.tgz",
      "integrity": "sha512-pgRc4hJ4/sNjWCSS9AmnS40x3bNMDTknHgL5UaMBTMyJnU90EgWh1Rz+MC9eFu4BuN/UwZjKQuY/1v3rM7HMfg==",
      "dependencies": {
        "define-data-property": "^1.3.0",
        "es-errors": "^1.3.0",
        "function-bind": "^1.1.2",
        "get-intrinsic": "^1.2.4",
        "gopd": "^1.0.1",
        "has-property-descriptors": "^1.0.2"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/setprototypeof": {
      "version": "1.2.0",
      "resolved": "https://registry.npmjs.org/setprototypeof/-/setprototypeof-1.2.0.tgz",
      "integrity": "sha512-E5LDX7Wrp85Kil5bhZv46j8jOeboKq5JM6YM3qPfMhEZHw9OC8ty7GezZG8NFUJg7eoOzSX5ygQY26pDoOKl+Q==",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/side-channel": {
      "version": "1.0.6",
      "resolved": "https://registry.npmjs.org/side-channel/-/side-channel-1.0.6.tgz",
      "integrity": "sha512-fDW/EZ6Q9RiO8eFG8Hj+7u/oW+xFrXvMoUR6nHHrIEX4MO5k5M2oiTo0xX0TzWWJrm5M0Y7b5dGkB4S0YzefA==",
      "dependencies": {
        "call-bind": "^1.0.7",
        "es-errors": "^1.5.0",
        "get-intrinsic": "^1.2.4",
        "object-inspect": "^1.13.1"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/split2": {
      "version": "4.2.0",
      "resolved": "https://registry.npmjs.org/split2/-/split2-4.2.0.tgz",
      "integrity": "sha512-UcjcJOWknrNkF6PLX83qcHM6KHgVKNkV62Y8a5uYDVv9ydGQVwAHMKqHdJje1VTWpljG0WYpCDhrCdAOYH4TWg==",
      "engines": {
        "node": ">= 10.x"
      }
    },
    "node_modules/statuses": {
      "version": "2.0.1",
      "resolved": "https://registry.npmjs.org/statuses/-/statuses-2.0.1.tgz",
      "integrity": "sha512-RwNA9Z/7PrK06rYLIzFMlaF+l73iwpzsqRIFgbMLbTcLD6cOao82TaWefPXQvB2fOC4AjuYSEndS7N/mTCbkdQ==",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/toidentifier": {
      "version": "1.0.1",
      "resolved": "https://registry.npmjs.org/toidentifier/-/toidentifier-1.0.1.tgz",
      "integrity": "sha512-o5ez+3G11YXxm06urDxPZkONtj7UOq9NMQf0gK33QJ9Q9Fq8hIhvAXGAh4phT90uvpw8OuBrPMz7a9QvAK5xQ==",
      "engines": {
        "node": ">=0.6"
      }
    },
    "node_modules/type-is": {
      "version": "1.6.18",
      "resolved": "https://registry.npmjs.org/type-is/-/type-is-1.6.18.tgz",
      "integrity": "sha512-TkRKr9sUTxEH8MdfuCSP7VizJyzRNMjj2J2do2Jr3Kym598JVdEksuzxQCnlFPuj47V0u8Bn8Uwjovii3xQbQ==",
      "dependencies": {
        "media-typer": "0.3.0",
        "mime-types": "~2.1.24"
      },
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/unpipe": {
      "version": "1.0.0",
      "resolved": "https://registry.npmjs.org/unpipe/-/unpipe-1.0.0.tgz",
      "integrity": "sha512-pjy2bYhSsufwWlKwPc+l3cN7+wuJacrT4ZydFqx63FIo4eI1rNyXeO5zw78C6Ss1FzeqNh7PMedjE6w392/k6Q==",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/utils-merge": {
      "version": "1.0.1",
      "resolved": "https://registry.npmjs.org/utils-merge/-/utils-merge-1.0.1.tgz",
      "integrity": "sha512-pDVKh4rM2bE+gvdP9vDjGV48ujim3Q2KEsYL0KiR02PUMuG7+TCiIydCkJ3v9n8jB8a8O8poAb6ZV5H28bLX4g==",
      "engines": {
        "node": ">= 0.4.0"
      }
    },
    "node_modules/vary": {
      "version": "1.1.2",
      "resolved": "https://registry.npmjs.org/vary/-/vary-1.1.2.tgz",
      "integrity": "sha512-BNGbWLfd0eUPabhkXUVm0j8uuvREyTh5ovRa/dyow/BqAbZJyC+5fU+IzQOzmAKzYqYRAISoRhdQr3eIZ/PXqg==",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/xtend": {
      "version": "4.0.2",
      "resolved": "https://registry.npmjs.org/xtend/-/xtend-4.0.2.tgz",
      "integrity": "sha512-LKYU1iAXJXUgAXn9URsgmvmMIIk176thU+Z9d30EX8SynQbH0bR4xL0DZ8wZYlrSchIIvY6FmdhDuWNesJj9Jw==",
      "engines": {
        "node": ">=0.4"
      }
    }
  }
}
```

### `backend/Dockerfile`
```dockerfile
# syntax=docker/dockerfile:1.7

FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY src ./src

FROM gcr.io/distroless/nodejs22-debian12 AS runtime

WORKDIR /app

COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/src ./src

ENV NODE_ENV=production
ENV PORT=3000

EXPOSE 3000

CMD ["src/server.js"]
```

### `backend/src/server.js`
```javascript
import express from "express";
import pg from "pg";

const { Pool } = pg;

const app = express();
const port = Number(process.env.PORT || 3000);

const databaseUrl = process.env.DATABASE_URL;

if (!databaseUrl) {
  throw new Error("DATABASE_URL is required");
}

const pool = new Pool({
  connectionString: databaseUrl,
  max: 10,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000
});

app.use(express.json());

app.get("/health", async (_request, response) => {
  try {
    await pool.query("SELECT 1");
    response.json({
      status: "ok",
      database: "connected"
    });
  } catch (error) {
    response.status(503).json({
      status: "error",
      database: "disconnected",
      message: error.message
    });
  }
});

app.get("/api/items", async (_request, response, next) => {
  try {
    const result = await pool.query(
      `SELECT id, name, value, created_at
       FROM items
       ORDER BY created_at DESC, id DESC`
    );

    response.json(result.rows);
  } catch (error) {
    next(error);
  }
});

app.post("/api/items", async (request, response, next) => {
  const { name, value } = request.body;

  if (!name || typeof name !== "string" || name.trim().length === 0) {
    response.status(400).json({
      message: "name is required and must be a non-empty string"
    });
    return;
  }

  try {
    const result = await pool.query(
      `INSERT INTO items (name, value)
       VALUES ($1, $2)
       RETURNING id, name, value, created_at`,
      [name.trim(), value ?? null]
    );

    response.status(201).json(result.rows[0]);
  } catch (error) {
    next(error);
  }
});

app.use((error, _request, response, _next) => {
  console.error(error);

  response.status(500).json({
    message: "Internal server error"
  });
});

async function waitForDatabase() {
  const maxAttempts = 30;
  const delayMs = 1000;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      await pool.query("SELECT 1");
      console.log("Database connection established");
      return;
    } catch (error) {
      console.log(`Waiting for database: attempt ${attempt}/${maxAttempts}`);
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }

  throw new Error("Database did not become ready in time");
}

async function initializeDatabase() {
  await pool.query(
    `CREATE TABLE IF NOT EXISTS items (
       id SERIAL PRIMARY KEY,
       name TEXT NOT NULL,
       value TEXT,
       created_at TIMESTAMP NOT NULL DEFAULT NOW()
     )`
  );
}

async function start() {
  await waitForDatabase();
  await initializeDatabase();

  app.listen(port, "0.0.0.0", () => {
    console.log(`Backend service listening on port ${port}`);
  });
}

start().catch((error) => {
  console.error(error);
  process.exit(1);
});
```

---

### `frontend/package.json`
```json
{
  "name": "data-storage-frontend",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "vite build",
    "preview": "vite preview --host 0.0.0.0"
  },
  "dependencies": {
    "@vitejs/plugin-react": "latest",
    "vite": "latest",
    "react": "latest",
    "react-dom": "latest"
  },
  "devDependencies": {}
}
```

### `frontend/package-lock.json`
```json
{
  "name": "data-storage-frontend",
  "version": "1.0.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "data-storage-frontend",
      "version": "1.0.0",
      "dependencies": {
        "@vitejs/plugin-react": "latest",
        "vite": "latest",
        "react": "latest",
        "react-dom": "latest"
      }
    }
  }
}
```

### `frontend/Dockerfile`
```dockerfile
# syntax=docker/dockerfile:1.7

FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY index.html ./
COPY src ./src

RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### `frontend/nginx.conf`
```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://backend:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### `frontend/index.html`
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Data Storage Microservices</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

### `frontend/src/main.jsx`
```jsx
import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    throw new Error(data?.message || `Request failed with status ${response.status}`);
  }

  return data;
}

function App() {
  const [items, setItems] = useState([]);
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadItems() {
    try {
      const data = await fetchJson("/api/items");
      setItems(data);
      setError("");
    } catch (loadError) {
      setError(loadError.message);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();

    try {
      setError("");
      setMessage("");

      await fetchJson("/api/items", {
        method: "POST",
        body: JSON.stringify({
          name,
          value
        })
      });

      setName("");
      setValue("");
      setMessage("Item saved successfully.");
      await loadItems();
    } catch (saveError) {
      setError(saveError.message);
    }
  }

  useEffect(() => {
    loadItems();
  }, []);

  return (
    <main className="app">
      <section className="card">
        <h1>Data Storage Microservices</h1>
        <p>
          A decoupled full-stack application with a frontend service, backend service,
          and PostgreSQL database service.
        </p>

        <form onSubmit={handleSubmit} className="form">
          <label>
            Name
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Example item"
              required
            />
          </label>

          <label>
            Value
            <input
              value={value}
              onChange={(event) => setValue(event.target.value)}
              placeholder="Optional value"
            />
          </label>

          <button type="submit">Save Item</button>
        </form>

        {message && <p className="success">{message}</p>}
        {error && <p className="error">{error}</p>}
      </section>

      <section className="card">
        <div className="header-row">
          <h2>Saved Items</h2>
          <button type="button" onClick={loadItems}>
            Refresh
          </button>
        </div>

        <div className="items">
          {items.length === 0 ? (
            <p className="empty">No items stored yet.</p>
          ) : (
            items.map((item) => (
              <article className="item" key={item.id}>
                <div>
                  <strong>{item.name}</strong>
                  <span>{item.value || "No value provided"}</span>
                </div>
                <small>{new Date(item.created_at).toLocaleString()}</small>
              </article>
            ))
          )}
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
```

### `frontend/src/styles.css`
```css
:root {
  color-scheme: light;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #eef2f7;
  color: #172033;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
}

button,
input {
  font: inherit;
}

button {
  border: 0;
  border-radius: 12px;
  background: #2563eb;
  color: white;
  cursor: pointer;
  font-weight: 700;
  padding: 0.75rem 1rem;
}

button:hover {
  background: #1d4ed8;
}

.app {
  display: grid;
  gap: 1.5rem;
  margin: 0 auto;
  max-width: 960px;
  padding: 3rem 1rem;
}

.card {
  background: white;
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.12);
  padding: 2rem;
}

.form {
  display: grid;
  gap: 1rem;
  margin-top: 1.5rem;
}

label {
  display: grid;
  font-weight: 700;
  gap: 0.5rem;
}

input {
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  padding: 0.8rem 1rem;
}

.header-row {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}

.items {
  display: grid;
  gap: 1rem;
  margin-top: 1.5rem;
}

.item {
  align-items: center;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem;
}

.item div {
  display: grid;
  gap: 0.25rem;
}

.item span {
  color: #475569;
}

.empty,
.success,
.error {
  margin-bottom: 0;
}

.success {
  color: #15803d;
}

.error {
  color: #b91c1c;
}

@media (min-width: 768px) {
  .form {
    grid-template-columns: 1fr 1fr auto;
    align-items: end;
  }
}
```

# Checker Review
## Review Verdict: **Partially compliant — not perfect**

### Multi-stage builds
✅ **Yes.** Both custom services use multi-stage Dockerfiles:

- `backend/Dockerfile`: `node:22-alpine AS builder` → `gcr.io/distroless/nodejs22-debian12 AS runtime`
- `frontend/Dockerfile`: `node:20-alpine AS builder` → `nginx:1.27-alpine AS runtime`

### Minimal images
✅ **Mostly.**

- Backend final image uses **distroless**, which satisfies the minimal-image requirement.
- Frontend final image uses **nginx:alpine**, which is lightweight but not the absolute smallest possible. A static distroless/scratch-style serving approach would be stricter.
- Database uses `postgres:16-alpine`, which is appropriate.

⚠️ Warning: the spec says to prioritize the **absolute smallest** images possible. `nginx:alpine` is acceptable, but not maximally minimal.

### Single `docker-compose.yml`
✅ **Yes.** There is one root-level `docker-compose.yml` orchestrating:

- `frontend`
- `backend`
- `database`

It also defines a bridge network and PostgreSQL volume.

## Critical Warnings

1. **Frontend build is likely broken.**
   - `frontend/package-lock.json` is incomplete and does not include dependency entries for `vite`, `react`, `react-dom`, or `@vitejs/plugin-react`.
   - `npm ci` in `frontend/Dockerfile` will likely fail.

2. **Frontend Vite configuration is missing.**
   - `@vitejs/plugin-react` is listed, but no `vite.config.js` is provided.
   - Add a Vite config if the React plugin is intended to be used.

3. **Frontend dependencies should usually be dev dependencies.**
   - `vite` and `@vitejs/plugin-react` should normally be in `devDependencies`.
   - If moved there, the frontend Dockerfile should not use `--omit=dev` during the build stage, or should install dev dependencies only in the builder stage.

4. **Compose startup is functional but not health-gated.**
   - `depends_on` only ensures container start order, not readiness.
   - The backend has its own database retry logic, so this is mitigated, but explicit health checks would be better.

## Summary

The architecture and compose setup mostly match the spec. Multi-stage builds are present, images are mostly minimal, and there is a single root-level `docker-compose.yml`. However, the generated frontend package/lockfile issue means the application may not successfully build with `docker-compose up --build`, so it does **not perfectly match** the original spec until fixed.