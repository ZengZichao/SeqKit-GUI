// Command spec-dumper walks seqkit's own cobra command tree and writes a JSON
// description of every subcommand and flag to stdout.
//
// Flag names, shorthands, types, defaults and usage strings all come from the
// flags seqkit registers with pflag, so the generated schema cannot drift from
// the CLI it drives.
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"reflect"
	"runtime"

	"github.com/shenwei356/seqkit/v2/seqkit/cmd"
	"github.com/spf13/cobra"
	"github.com/spf13/pflag"
)

type flagSpec struct {
	Name        string   `json:"name"`
	Shorthand   string   `json:"shorthand,omitempty"`
	Type        string   `json:"type"`
	Default     string   `json:"default"`
	Usage       string   `json:"usage"`
	Hidden      bool     `json:"hidden,omitempty"`
	NoOptDef    string   `json:"no_opt_default,omitempty"`
	Required    bool     `json:"required,omitempty"`
	IsGlobal    bool     `json:"global,omitempty"`
	Annotations []string `json:"annotations,omitempty"`
}

type commandSpec struct {
	Name        string        `json:"name"`
	Use         string        `json:"use"`
	UseLine     string        `json:"use_line"`
	Path        []string      `json:"path"`
	Short       string        `json:"short"`
	Long        string        `json:"long"`
	Example     string        `json:"example,omitempty"`
	Aliases     []string      `json:"aliases,omitempty"`
	Group       string        `json:"group,omitempty"`
	Hidden      bool          `json:"hidden,omitempty"`
	Deprecated  string        `json:"deprecated,omitempty"`
	Runnable    bool          `json:"runnable"`
	ArgsMatcher string        `json:"args_matcher,omitempty"`
	ValidArgs   []string      `json:"valid_args,omitempty"`
	Flags       []flagSpec    `json:"flags"`
	GlobalFlags []flagSpec    `json:"global_flags"`
	Sub         []commandSpec `json:"subcommands,omitempty"`
}

type groupSpec struct {
	ID    string `json:"id"`
	Title string `json:"title"`
}

type dump struct {
	SeqkitVersion string        `json:"seqkit_version"`
	Groups        []groupSpec   `json:"groups"`
	Commands      []commandSpec `json:"commands"`
}

func matcherName(matcher cobra.PositionalArgs) string {
	if matcher == nil {
		return ""
	}
	fn := runtime.FuncForPC(reflect.ValueOf(matcher).Pointer())
	if fn == nil {
		return ""
	}
	return fn.Name()
}

func specOf(flag *pflag.Flag, global bool) flagSpec {
	spec := flagSpec{
		Name:      flag.Name,
		Shorthand: flag.Shorthand,
		Type:      flag.Value.Type(),
		Default:   flag.DefValue,
		Usage:     flag.Usage,
		Hidden:    flag.Hidden,
		NoOptDef:  flag.NoOptDefVal,
		IsGlobal:  global,
	}
	if flag.Annotations != nil {
		if _, ok := flag.Annotations[cobra.BashCompOneRequiredFlag]; ok {
			spec.Required = true
		}
		for key, values := range flag.Annotations {
			spec.Annotations = append(spec.Annotations, key+"="+join(values))
		}
	}
	return spec
}

func join(values []string) string {
	out := ""
	for i, v := range values {
		if i > 0 {
			out += ","
		}
		out += v
	}
	return out
}

// specsOf keeps pflag's declaration order, which is how seqkit groups related
// options in its source files.
func specsOf(set *pflag.FlagSet, global bool) []flagSpec {
	set.SortFlags = false
	specs := make([]flagSpec, 0, set.NFlag())
	set.VisitAll(func(flag *pflag.Flag) {
		specs = append(specs, specOf(flag, global))
	})
	return specs
}

func walk(c *cobra.Command, parents []string, globalSpecs []flagSpec) commandSpec {
	path := append(append([]string{}, parents...), c.Name())

	local := specsOf(c.LocalFlags(), false)
	declared := map[string]bool{}
	for _, spec := range local {
		declared[spec.Name] = true
	}
	inherited := []flagSpec{}
	for _, spec := range globalSpecs {
		if !declared[spec.Name] {
			inherited = append(inherited, spec)
		}
	}

	spec := commandSpec{
		Name:        c.Name(),
		Use:         c.Use,
		UseLine:     c.UseLine(),
		Path:        path,
		Short:       c.Short,
		Long:        c.Long,
		Example:     c.Example,
		Aliases:     c.Aliases,
		Group:       c.GroupID,
		Hidden:      c.Hidden,
		Deprecated:  c.Deprecated,
		Runnable:    c.Runnable(),
		ArgsMatcher: matcherName(c.Args),
		ValidArgs:   c.ValidArgs,
		Flags:       local,
		GlobalFlags: inherited,
	}

	children := c.Commands()
	for _, child := range children {
		spec.Sub = append(spec.Sub, walk(child, path, inherited))
	}
	return spec
}

func main() {
	root := cmd.RootCmd
	root.Flags().SortFlags = false
	root.PersistentFlags().SortFlags = false

	d := dump{SeqkitVersion: cmd.VERSION}
	for _, g := range root.Groups() {
		d.Groups = append(d.Groups, groupSpec{ID: g.ID, Title: g.Title})
	}

	globals := specsOf(root.PersistentFlags(), true)
	for _, child := range root.Commands() {
		d.Commands = append(d.Commands, walk(child, []string{root.Name()}, globals))
	}

	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(d); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
