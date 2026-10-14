package {{package}}.config;

import java.net.URI;
import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.OptimisticLockingFailureException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;

import {{package}}.service.NotFoundException;

/**
 * One place that turns exceptions into RFC 9457 problem responses. Details that could help an attacker
 * (SQL, stack traces, internal names) are logged with a correlation id and never returned.
 */
@RestControllerAdvice
public class ApiExceptionHandler extends ResponseEntityExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    @ExceptionHandler(NotFoundException.class)
    ProblemDetail notFound(NotFoundException ex) {
        ProblemDetail p = ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, "The requested resource does not exist.");
        p.setTitle("Not found");
        p.setType(URI.create("urn:problem:not-found"));
        return p;
    }

    @ExceptionHandler(OptimisticLockingFailureException.class)
    ProblemDetail conflict(OptimisticLockingFailureException ex) {
        ProblemDetail p = ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, "The record was changed by someone else. Reload and try again.");
        p.setTitle("Conflict");
        p.setType(URI.create("urn:problem:concurrent-update"));
        return p;
    }

    @ExceptionHandler(DataIntegrityViolationException.class)
    ProblemDetail integrity(DataIntegrityViolationException ex) {
        String id = correlationId();
        log.warn("data integrity violation [{}]", id, ex);
        ProblemDetail p = ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, "The request conflicts with existing data.");
        p.setTitle("Conflict");
        p.setType(URI.create("urn:problem:data-conflict"));
        p.setProperty("correlationId", id);
        return p;
    }

    /** Method security throws inside the controller; without this the catch-all below would turn a 403 into a 500. */
    @ExceptionHandler(AccessDeniedException.class)
    ProblemDetail forbidden(AccessDeniedException ex) {
        ProblemDetail p = ProblemDetail.forStatusAndDetail(HttpStatus.FORBIDDEN, "You are not allowed to do this.");
        p.setTitle("Forbidden");
        p.setType(URI.create("urn:problem:forbidden"));
        return p;
    }

    @ExceptionHandler(AuthenticationException.class)
    ProblemDetail unauthorized(AuthenticationException ex) {
        ProblemDetail p = ProblemDetail.forStatusAndDetail(HttpStatus.UNAUTHORIZED, "Authentication is required.");
        p.setTitle("Unauthorized");
        p.setType(URI.create("urn:problem:unauthorized"));
        return p;
    }

    @ExceptionHandler(Exception.class)
    ProblemDetail unexpected(Exception ex) {
        String id = correlationId();
        log.error("unexpected error [{}]", id, ex);
        ProblemDetail p = ProblemDetail.forStatusAndDetail(HttpStatus.INTERNAL_SERVER_ERROR, "Something went wrong. Quote the correlation id when you contact support.");
        p.setTitle("Internal error");
        p.setType(URI.create("urn:problem:internal"));
        p.setProperty("correlationId", id);
        return p;
    }

    private static String correlationId() {
        return UUID.randomUUID().toString();
    }
}
