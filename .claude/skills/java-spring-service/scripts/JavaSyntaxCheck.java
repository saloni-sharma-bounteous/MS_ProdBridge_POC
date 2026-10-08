import com.sun.source.util.JavacTask;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

/**
 * Parse-only syntax check of every .java file under a folder. Needs no dependencies, so it works before Maven
 * has downloaded anything. It proves the files are valid Java; it does NOT prove they compile against Spring.
 * Run: java scripts/JavaSyntaxCheck.java <folder>      (requires a JDK, or a JRE with the jdk.compiler module)
 */
public class JavaSyntaxCheck {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            System.err.println("usage: java JavaSyntaxCheck.java <folder>");
            System.exit(2);
        }
        Path root = Paths.get(args[0]);
        List<File> files;
        try (Stream<Path> s = Files.walk(root)) {
            files = s.filter(p -> p.toString().endsWith(".java")).map(Path::toFile).sorted().collect(Collectors.toList());
        }
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) {
            System.err.println("no Java compiler available (need a JDK, or a JRE that includes jdk.compiler)");
            System.exit(2);
        }
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        try (StandardJavaFileManager fm = compiler.getStandardFileManager(diagnostics, null, null)) {
            JavacTask task = (JavacTask) compiler.getTask(null, fm, diagnostics, List.of("-proc:none"), null,
                fm.getJavaFileObjectsFromFiles(files));
            task.parse();
        }
        int errors = 0;
        for (Diagnostic<? extends JavaFileObject> d : diagnostics.getDiagnostics()) {
            if (d.getKind() == Diagnostic.Kind.ERROR) {
                errors++;
                System.out.println(d.getSource().getName() + ":" + d.getLineNumber() + ": " + d.getMessage(null));
            }
        }
        System.out.println(files.size() + " files parsed, " + errors + " syntax errors");
        System.exit(errors == 0 ? 0 : 1);
    }
}
